# tt-payment — асинхронный сервис процессинга платежей

Микросервис принимает запросы на оплату, асинхронно обрабатывает их через эмуляцию
внешнего платёжного шлюза и уведомляет клиента о результате через webhook.

## Как это работает

```
POST /api/v1/payments
        │
        │ одна транзакция: payments + outbox
        ▼
   ┌──────────┐      ┌────────────────────┐   publish   ┌────────────────────┐
   │ payments │      │ outbox-dispatcher  │────────────▶│ exchange: payments │
   │  outbox  │◀────▶│  (воркер, polling) │             └─────────┬──────────┘
   └──────────┘      └────────────────────┘                       │ payments.new
                                                                  ▼
                                                        ┌────────────────────┐
                                                        │ queue: payments.new│
                                                        └─────────┬──────────┘
                                                                  ▼
                                                          ┌───────────────┐
                                                          │   consumer    │
                                                          └───┬───────┬───┘
                        обработка 2–5 сек, 90% success        │       │
                        UPDATE payments.status ◀──────────────┘       │
                        POST webhook_url (одна попытка) ◀─────────────┘
                                    │
                                    │ не доставлен: next_webhook_retry_at
                                    ▼
                          ┌────────────────────┐
                          │   webhook-retry    │ повтор по расписанию
                          └────────────────────┘
```

1. `POST /api/v1/payments` в одной транзакции пишет платёж в `payments`
   и событие в `outbox` (**outbox pattern** — событие не может потеряться,
   даже если RabbitMQ недоступен), отвечает `202 Accepted`.
2. Воркер `outbox-dispatcher` опрашивает таблицу `outbox`, публикует события
   в exchange `payments` с routing key `payments.new` и помечает их published.
3. Consumer читает очередь `payments.new`: эмулирует обработку платежа
   (2–5 секунд, 90% успех / 10% ошибка), обновляет статус в БД и делает
   одну попытку доставки webhook на `webhook_url`.
4. Неудачная попытка обработки уходит в очередь отложенного ретрая,
   окончательно упавшие сообщения — в Dead Letter Queue.
5. Недоставленный webhook подхватывает воркер `webhook-retry` по
   `next_webhook_retry_at` — consumer не ждёт повторных попыток.

## Стек

FastAPI + Pydantic v2, SQLAlchemy 2.0 (async), PostgreSQL, RabbitMQ (FastStream),
Alembic, aiohttp, dependency-injector, Docker + docker-compose.

## Быстрый старт

```bash
cp .env.example .env
docker compose up --build
```

Поднимаются шесть сервисов: `payments-db`, `rabbit-mq`, `api` (миграции + uvicorn),
`outbox-dispatcher`, `consumer`, `webhook-retry`.

| Сервис            | Адрес                                            |
|-------------------|--------------------------------------------------|
| API               | http://localhost:8080                            |
| Swagger UI        | http://localhost:8080/docs                       |
| RabbitMQ Management | http://localhost:15672 (guest / guest)         |
| PostgreSQL        | localhost:5432                                   |

## Переменные окружения

| Переменная                                            | По умолчанию | Описание                          |
|-------------------------------------------------------|--------------|-----------------------------------|
| `POSTGRES_HOST` / `POSTGRES_PORT`                     | —            | Хост и порт PostgreSQL            |
| `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` | —            | БД и учётные данные               |
| `RABBIT_HOST` / `RABBIT_PORT`                         | —            | Хост и порт RabbitMQ              |
| `RABBIT_USER` / `RABBIT_PASSWORD`                     | —            | Учётные данные RabbitMQ           |
| `API_KEY`                                             | —            | Ключ для заголовка `X-API-Key` (обязателен) |
| `CONSUMER_MAX_ATTEMPTS`                               | `3`          | Попыток обработки до DLQ          |
| `CONSUMER_PREFETCH_COUNT`                             | `10`         | Prefetch consumer'а               |
| `WEBHOOK_MAX_ATTEMPTS`                                | `3`          | Попыток доставки webhook          |
| `WEBHOOK_BASE_DELAY_SECONDS`                          | `2`          | База экспоненциальной задержки    |
| `WEBHOOK_TIMEOUT_SECONDS`                             | `10`         | Таймаут HTTP-запроса              |
| `WEBHOOK_RETRY_POLL_INTERVAL_SECONDS`                 | `1.0`        | Интервал опроса недоставленных    |
| `WEBHOOK_RETRY_BATCH_SIZE`                            | `100`        | Размер пачки за итерацию          |
| `WEBHOOK_RETRY_CLAIM_SECONDS`                         | `300`        | TTL блокировки платежа воркером   |
| `DISPATCH_POLL_INTERVAL_SECONDS`                      | `1.0`        | Интервал опроса outbox            |
| `MAX_OUTBOX_ATTEMPTS`                                 | `3`          | Попыток публикации события        |
| `OUTBOX_RETRY_BASE_DELAY_SECONDS`                     | `2`          | База экспоненциальной задержки outbox |
| `DISPATCH_BATCH_SIZE`                                 | `100`        | Размер пачки outbox за итерацию   |
| `CLAIM_RELEASE_SECONDS`                               | `300`        | TTL блокировки записи outbox      |

## API

Все эндпоинты требуют заголовок `X-API-Key`.

### Создание платежа

`POST /api/v1/payments/` — заголовок `Idempotency-Key` обязателен.

```bash
curl -X POST http://localhost:8080/api/v1/payments/ \
  -H "X-API-Key: 123" \
  -H "Idempotency-Key: order-42" \
  -H "Content-Type: application/json" \
  -d '{
        "amount": "1500.00",
        "currency": "RUB",
        "description": "Подписка Pro",
        "metadata": {"user_id": 17, "source": "web"},
        "webhook_url": "https://webhook.site/your-uuid"
      }'
```

`202 Accepted`:

```json
{
  "uuid": "0f1a2b3c-4d5e-6f70-8192-a3b4c5d6e7f8",
  "status": "pending",
  "created_at": "2026-08-09T12:00:00Z"
}
```

Повторный запрос с тем же `Idempotency-Key` вернёт `409 Conflict`, если пэйлод не совпадает,
или вернёт уже сущестующую запись при совпадении данных - дубль платежа не создаётся.

### Получение платежа

`GET /api/v1/payments/{payment_id}`

```bash
curl http://localhost:8080/api/v1/payments/0f1a2b3c-4d5e-6f70-8192-a3b4c5d6e7f8 \
  -H "X-API-Key: 123"
```

```json
{
  "payment_id": "0f1a2b3c-4d5e-6f70-8192-a3b4c5d6e7f8",
  "amount": "1500.00",
  "currency": "RUB",
  "description": "Подписка Pro",
  "metadata": {"user_id": 17, "source": "web"},
  "status": "succeeded",
  "webhook_url": "https://webhook.site/your-uuid",
  "webhook_status": "delivered",
  "webhook_attempts": 1,
  "next_webhook_retry_at": null,
  "created_at": "2026-08-09T12:00:00Z",
  "processed_at": "2026-08-09T12:00:04Z"
}
```

Статус меняется с `pending` на `succeeded` или `failed` через несколько секунд
после создания — как только consumer обработает сообщение.

### Webhook

После обработки consumer отправляет `POST` на `webhook_url`:

```json
{
  "delivery_id": "0f1a2b3c-4d5e-6f70-8192-a3b4c5d6e7f8",
  "payment_id": "0f1a2b3c-4d5e-6f70-8192-a3b4c5d6e7f8",
  "status": "succeeded",
  "processed_at": "2026-08-09T12:00:04Z"
}
```

`delivery_id` совпадает с `payment_id` и предназначен для дедупликации на стороне получателя.

Для ручной проверки удобно указать одноразовый URL с https://webhook.site.
Если `webhook_url` не передан, платёж обрабатывается без уведомления,
а `webhook_status` остаётся `null`.

#### Состояние доставки

Обработка платежа и доставка уведомления — разные вещи: платёж может быть
`succeeded`, а webhook при этом не доставлен. Поэтому состояние доставки
хранится в БД отдельно от статуса платежа и отдаётся в `GET /api/v1/payments/{id}`.

| Поле                    | Значение                                                        |
|-------------------------|-----------------------------------------------------------------|
| `webhook_status`        | `pending` → `delivered` / `failed`; `null` — уведомление не нужно |
| `webhook_attempts`      | Сколько попыток доставки сделано                                 |
| `next_webhook_retry_at` | Время следующей попытки, `null` в терминальном состоянии          |
| `webhook_last_error`    | Текст последней ошибки (не отдаётся в API)                        |

Запись создаётся сразу при создании платежа (`pending`, если задан `webhook_url`)
и обновляется после каждой попытки — короткой отдельной транзакцией,
уже после HTTP-запроса, чтобы не держать транзакцию открытой на время сети.

Consumer делает **одну** попытку доставки и не ждёт повторов: при неудаче он
проставляет `next_webhook_retry_at` и подтверждает сообщение. Дальше платёж
подхватывает воркер `webhook-retry` — он опрашивает `payments`, где
`webhook_status = pending` и `next_webhook_retry_at <= now`, забирает пачку
через `SELECT ... FOR UPDATE SKIP LOCKED`, сдвигает `next_webhook_retry_at`
вперёд (это и есть блокировка на время работы) и коммитит транзакцию **до**
HTTP-запроса. Тот же приём, что и в outbox-диспетчере: сеть никогда не
происходит внутри открытой транзакции.

HTTP-вызов спрятан за интерфейсом `IWebhookClient`; реализация на aiohttp
живёт в `infrastructure/http` и переиспользует один `ClientSession`.

## Топология RabbitMQ

| Объект                  | Тип      | Назначение                                                           |
|-------------------------|----------|----------------------------------------------------------------------|
| `payments`              | exchange | Основной обменник                                                     |
| `payments.new`          | queue    | Основная очередь, слушает consumer                                    |
| `payments.dlx`          | exchange | Dead letter exchange                                                  |
| `payments.new.retry.1`  | queue    | Отложенный ретрай, TTL 2 сек                                          |
| `payments.new.retry.2`  | queue    | Отложенный ретрай, TTL 4 сек                                          |
| `payments.new.dlq`      | queue    | Dead Letter Queue                                                     |

Retry-очереди никто не слушает: сообщение лежит в очереди `x-message-ttl`
миллисекунд, после чего по dead-letter-правилам возвращается в `payments`
→ `payments.new`. Это даёт экспоненциальную задержку (2 сек → 4 сек)
средствами самого брокера, без блокировки consumer'а.

## Retry и Dead Letter Queue

Номер попытки едет в заголовке сообщения `x-attempt`.

| Попытка | Результат ошибки                                          |
|---------|-----------------------------------------------------------|
| 1       | → `payments.new.retry.1`, повтор через 2 сек              |
| 2       | → `payments.new.retry.2`, повтор через 4 сек              |
| 3       | Финальная: платёж переводится в `failed`, клиент получает webhook |

В DLQ сообщение попадает, если на финальной попытке произошла инфраструктурная
ошибка (недоступна БД и т.п.), если платёж не найден в БД или если тело
сообщения не удалось разобрать.

Контракт DLQ единый для всех источников: тело — то сообщение, которое не удалось
обработать, причина и источник — в заголовках.

| Заголовок  | Значение                                              |
|------------|-------------------------------------------------------|
| `x-error`  | Причина попадания в DLQ                                |
| `x-source` | `consumer` — не обработали, `webhook` — не доставили   |
| `x-attempt`| Номер попытки обработки (только для `consumer`)         |

Consumer работает с `AckPolicy.MANUAL`: сообщение подтверждается только после
того, как результат зафиксирован — обработан, переложен в retry или отправлен
в DLQ. Если переложить сообщение не удалось, оно возвращается брокеру через
`nack(requeue=True)` и не теряется.

Доставка webhook ретраится независимо от обработки платежа — 3 попытки
с задержками 2 и 4 секунды.

| Попытка | Кто делает      | Результат ошибки                                    |
|---------|-----------------|-----------------------------------------------------|
| 1       | `consumer`      | `next_webhook_retry_at = now + 2s`, статус `pending` |
| 2       | `webhook-retry` | `next_webhook_retry_at = now + 4s`, статус `pending` |
| 3       | `webhook-retry` | `webhook_status = failed`, событие в DLQ             |

Каждая попытка фиксируется в `payments` (`webhook_attempts`, `webhook_last_error`,
`next_webhook_retry_at`). Статус самого платежа при этом не меняется — он уже
обработан, недоставленное уведомление это отдельная сущность.

## Идемпотентность

* `Idempotency-Key` — уникальный индекс в таблице `payments`, повторный запрос
  либо вернёт уже существующую запись с соответствующими данными либо получает `409`.
  не создаёт дубль в бд.
* Consumer перед обработкой берёт платёж с `SELECT ... FOR UPDATE` и проверяет
  `processed_at`. Повторная доставка того же сообщения (at-least-once) не
  приводит к повторному списанию — обработанный платёж возвращается как есть.

## Локальный запуск без Docker

Нужны запущенные PostgreSQL и RabbitMQ, в `.env` — их адреса.

```bash
poetry install
poetry run alembic upgrade head

poetry run uvicorn src.presentation.main:app --reload --port 8080
poetry run python -m src.workers.dispatcher
poetry run python -m src.workers.webhook_retry
poetry run faststream run src.workers.payment_consumer:app
```

## Миграции

```bash
poetry run alembic upgrade head
poetry run alembic revision --autogenerate -m "описание"
poetry run alembic downgrade -1
```

## Структура проекта

```
src/
├── application/            слой приложения: сущности, интерфейсы, сервисы
│   ├── outbox/             outbox-сущность и сервис публикации событий
│   ├── payment/            платежи: создание и обработка
│   └── webhook/            доставка webhook и ретрай недоставленных
├── core/                   конфигурация и базовое исключение
├── infrastructure/
│   ├── db/                 модели, менеджеры, UnitOfWork, миграции
│   ├── http/               aiohttp-клиент для webhook
│   └── rabbit/             топология, publisher, consumer
├── presentation/           FastAPI: роутеры, схемы, DI-контейнер, аутентификация
└── workers/                точки входа: dispatcher, consumer, webhook-retry
```

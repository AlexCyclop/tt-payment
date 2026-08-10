FROM python:3.13-slim-bullseye as base
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    VIRTUAL_ENV=/payment/venv

WORKDIR /payment/app

COPY ./poetry.lock ./pyproject.toml ./

RUN python -m pip install --no-cache-dir "poetry==2.1.2" \
    && python -m venv --copies "${VIRTUAL_ENV}" \
    && . "${VIRTUAL_ENV}/bin/activate" \
    && poetry install --no-root

FROM python:3.13-slim-bullseye as final

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    VIRTUAL_ENV=/payment/venv

WORKDIR /payment/app

COPY --from=base ${VIRTUAL_ENV} ${VIRTUAL_ENV}

COPY . .

ENV PATH="${VIRTUAL_ENV}/bin:$PATH"

CMD ["uvicorn", "src.presentation.main:app", "--host", "0.0.0.0", "--port", "8080"]

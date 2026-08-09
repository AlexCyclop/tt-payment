from uuid import UUID

from dependency_injector.wiring import inject, Provide
from fastapi import APIRouter, Depends, Header
from starlette import status

from src.application.payment.entities import CreatePaymentRequestDTO
from src.application.payment.services.payment import PaymentService
from src.presentation.api.v1.schemas.payment import (
    CreatePaymentRequestSchema,
    CreatePaymentResponseSchema,
    GetPaymentResponseSchema,
)
from src.presentation.containers import Container

payments_router = APIRouter(tags=["payments"], prefix="/payments")


@payments_router.post(
    "/",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=CreatePaymentResponseSchema,
)
@inject
async def create_payment(
    payment: CreatePaymentRequestSchema,
    payment_service: PaymentService = Depends(Provide[Container.payment_service]),
    idempotency_key: str = Header(
        min_length=1, max_length=255, alias="Idempotency-Key"
    ),
):
    return await payment_service.create_payment(
        CreatePaymentRequestDTO(**payment.model_dump()), idempotency_key
    )


@payments_router.get("/{payment_id}", response_model=GetPaymentResponseSchema)
@inject
async def get_payment(
    payment_id: UUID,
    payment_service: PaymentService = Depends(Provide[Container.payment_service]),
):
    return await payment_service.get_payment(payment_id)

from fastapi import APIRouter

from src.presentation.api.v1.endpoints.payment import payments_router

v1_router = APIRouter(prefix="/v1")
v1_router.include_router(payments_router)

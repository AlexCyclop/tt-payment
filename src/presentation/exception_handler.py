from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from src.core.default_exception import DefaultException


async def default_exception_handler(
    request: Request, exc: DefaultException
) -> Response:
    return JSONResponse(
        status_code=exc.status_code, content={"error": exc.message, **exc.detail}
    )

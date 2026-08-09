from fastapi import FastAPI, Security

from src.presentation.auth import verify_api_key
from src.presentation.containers import Container
from src.core.default_exception import DefaultException
from src.presentation.api.router import api_router
from src.presentation.exception_handler import default_exception_handler


def create_app():
    fastapi_app = FastAPI(dependencies=[Security(verify_api_key)])
    container = Container()
    container.wire(packages=["src.presentation.api"])
    fastapi_app.include_router(api_router)
    fastapi_app.add_exception_handler(DefaultException, default_exception_handler)

    return fastapi_app


app = create_app()


@app.get("/")
async def hello():
    return {"message": "hello there"}

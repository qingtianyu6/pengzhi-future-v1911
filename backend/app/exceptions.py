from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.services.errors import ServiceError


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ServiceError)
    async def service_exception_handler(
        _request: Request, exception: ServiceError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exception.status_code,
            content={
                "code": exception.status_code,
                "message": exception.message,
                "data": None,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        _request: Request, exception: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "code": 422,
                "message": "请求参数校验失败",
                "data": {"errors": jsonable_encoder(exception.errors())},
            },
        )

    @app.exception_handler(Exception)
    async def unexpected_exception_handler(
        _request: Request, _exception: Exception
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"code": 500, "message": "服务器内部错误", "data": None},
        )

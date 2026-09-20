from typing import Generic, TypeVar

from pydantic import BaseModel


DataT = TypeVar("DataT")


class ApiResponse(BaseModel, Generic[DataT]):
    code: int = 200
    message: str = "success"
    data: DataT


class PaginatedData(BaseModel, Generic[DataT]):
    items: list[DataT]
    total: int
    page: int
    page_size: int

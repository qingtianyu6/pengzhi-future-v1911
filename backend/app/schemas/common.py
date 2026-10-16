from typing import Generic, TypeVar

from datetime import UTC, datetime
import re
from pydantic import BaseModel, model_serializer


DataT = TypeVar("DataT")


class ApiResponse(BaseModel, Generic[DataT]):
    code: int = 200
    message: str = "success"
    data: DataT

    @model_serializer(mode="wrap")
    def serialize_utc(self, handler):
        # SQLite stores UTC datetimes without tzinfo. Annotate them at the wire boundary.
        def normalize(value):
            if isinstance(value, datetime):
                return value.replace(tzinfo=UTC) if value.tzinfo is None else value
            if isinstance(value, dict):
                return {key: normalize(item) for key, item in value.items()}
            if isinstance(value, (tuple, list)):
                return [normalize(item) for item in value]
            if isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?", value):
                return value + "Z"
            return value
        return normalize(handler(self))


class PaginatedData(BaseModel, Generic[DataT]):
    items: list[DataT]
    total: int
    page: int
    page_size: int

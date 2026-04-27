"""Common response envelope."""
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


class ResponseMeta(BaseModel):
    cached: bool = False
    query_time_ms: int = 0
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class APIResponse(BaseModel):
    status: str = 'ok'
    data: Any = None
    meta: ResponseMeta = Field(default_factory=ResponseMeta)


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    status: str = 'error'
    error: ErrorDetail

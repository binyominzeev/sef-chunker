"""Pydantic schemas for request/response validation."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class BookCreate(BaseModel):
    sefaria_ref: str


class BookResponse(BaseModel):
    id: int
    title: str
    sefaria_ref: str
    created_at: datetime
    chunk_count: int = 0

    model_config = {"from_attributes": True}


class ChunkResponse(BaseModel):
    id: int
    book_id: int
    chunk_number: int
    start_ref: Optional[str]
    end_ref: Optional[str]
    hebrew_text: str
    estimated_tokens: int

    model_config = {"from_attributes": True}


class SummaryResponse(BaseModel):
    id: int
    chunk_id: int
    prompt: str
    summary: str
    generated_at: datetime
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float

    model_config = {"from_attributes": True}


class ChunkRequest(BaseModel):
    book_id: int
    mode: str  # "equal" or "char_count"
    num_days: Optional[int] = None
    char_count: Optional[int] = None


class PromptLabRequest(BaseModel):
    book_id: int
    chunk_id: int
    model: str = "gpt-4o-mini"
    temperature: float = 0.7
    prompt: str


class SettingUpdate(BaseModel):
    key: str
    value: str


class TelegramTestRequest(BaseModel):
    message: str = "Test message from Sefaria Daily AI 📖"

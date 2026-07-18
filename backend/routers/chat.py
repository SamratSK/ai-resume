"""Read-only per-JD hybrid RAG chat endpoint."""
from __future__ import annotations

from typing import List, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend import state
from backend.routers.jds import _jd_path

router = APIRouter(prefix="/api/jds", tags=["chat"])


class HistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=12000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    history: List[HistoryMessage] = Field(default_factory=list, max_length=30)


class ChatSourceResponse(BaseModel):
    resume_id: str
    name: str


class ChatResponse(BaseModel):
    answer: str
    sources: List[ChatSourceResponse]
    route_taken: Literal["structured", "semantic", "hybrid"]


@router.post("/{jd_id}/chat", response_model=ChatResponse)
def chat(jd_id: str, payload: ChatRequest) -> ChatResponse:
    if not _jd_path(jd_id).exists():
        raise HTTPException(404, f"JD '{jd_id}' not found")
    result = state.chat_service.ask(
        jd_id,
        payload.message.strip(),
        [message.model_dump() for message in payload.history],
    )
    return ChatResponse(
        answer=result.answer,
        sources=[ChatSourceResponse(resume_id=source.resume_id, name=source.name) for source in result.sources],
        route_taken=result.route_taken,
    )

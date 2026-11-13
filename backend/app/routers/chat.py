"""Authenticated chat with the local Ollama runtime."""
import json
import re
from threading import BoundedSemaphore
from typing import Literal
from uuid import UUID
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ..deps import current_user, require
from ..errors import ApiError, forbidden
from ..services.hull_chat import call_tool, hull_reply
from ..services.inquiries import MENU
from ..services.common import WRITE

router = APIRouter(prefix="/api", tags=["chat"])
MODEL = "qwen2.5:1.5b-instruct"
ollama = build_opener(ProxyHandler({}))
generation = BoundedSemaphore(1)


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2000)


class FeedbackIn(BaseModel):
    kind: Literal["suggestion", "inquiry"]
    content: str = Field(min_length=1, max_length=2000)
    request_id: UUID


@router.post("/chat/feedback", status_code=201)
def feedback(body: FeedbackIn, user=Depends(require(MENU, WRITE))):
    if not body.content.strip():
        raise ApiError(400, "FEEDBACK_INPUT", "접수할 내용을 입력해 주세요.")
    result = call_tool(user["emp_no"], "submit_feedback", body.model_dump(mode="json"))
    if result.get("forbidden"):
        raise forbidden(MENU)
    return result


class ChatIn(BaseModel):
    messages: list[Message] = Field(min_length=1, max_length=12)


@router.post("/chat")
def chat(body: ChatIn, user=Depends(current_user)):
    if body.messages[-1].role != "user":
        raise ApiError(400, "CHAT_INPUT", "질문을 입력해 주세요.")
    if re.fullmatch(r"(건의|문의)(?:하기|\s*하고\s*싶어)?[.!?]?", body.messages[-1].content.strip()):
        kind = "suggestion" if body.messages[-1].content.strip().startswith("건의") else "inquiry"
        return {"answer": "접수할 내용을 입력하고 접수 버튼을 눌러 주세요.", "feedback_kind": kind}
    reply = hull_reply(body.messages[-1].content, user["emp_no"])
    if reply is not None:
        return reply
    payload = {
        "model": MODEL,
        "stream": False,
        "options": {"num_ctx": 4096, "num_predict": 320},
        "messages": [
            {"role": "system", "content": "당신은 조선소 업무 용어와 작업을 설명하는 안내 챗봇입니다. "
             "한국어로 간결하게 답하세요. 시스템의 실제 호선·공정 데이터에 접근할 수 없습니다. "
             "실제 현황은 추측하지 말고 호선 목록이나 상세 화면에서 확인하도록 안내하세요."},
            *[item.model_dump() for item in body.messages],
        ],
    }
    request = Request("http://127.0.0.1:11434/api/chat", json.dumps(payload).encode(),
                      {"Content-Type": "application/json"})
    if not generation.acquire(blocking=False):
        raise ApiError(429, "CHAT_BUSY", "다른 답변을 작성 중입니다. 잠시 후 다시 보내 주세요.")
    try:
        with ollama.open(request, timeout=90) as response:
            answer = json.load(response)["message"]["content"].strip()
        if not answer:
            raise ValueError("Empty answer")
        return {"answer": answer}
    except HTTPError as exc:
        if exc.code == 404:
            raise ApiError(503, "CHAT_MODEL_MISSING", "로컬 채팅 모델을 찾을 수 없습니다.") from exc
        raise ApiError(502, "CHAT_MODEL_ERROR", "로컬 모델이 응답을 만들지 못했습니다.") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise ApiError(503, "CHAT_OFFLINE", "로컬 모델에 연결할 수 없습니다. Ollama 실행 상태를 확인해 주세요.") from exc
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        raise ApiError(502, "CHAT_RESPONSE", "로컬 모델의 답변을 읽을 수 없습니다.") from exc
    finally:
        generation.release()

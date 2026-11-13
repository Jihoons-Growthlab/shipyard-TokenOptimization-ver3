"""사용 로그·건의·문의 라우터(명세 외 요청 기능)."""
from fastapi import APIRouter, Depends, Response

from ..db import get_db
from ..deps import require
from ..schemas import InquiryIn
from ..services import inquiries, usage
from ..services.common import ADMIN, WRITE

router = APIRouter(prefix="/api", tags=["usage"])
A = require("M92", ADMIN)
Q = require(inquiries.MENU, WRITE)


@router.get("/usage/summary")
def usage_summary(days: int = 7, emp_no: str | None = None, _=Depends(A), conn=Depends(get_db)):
    return usage.summary(conn, days, emp_no or None)


@router.get("/inquiries")
def list_inquiries(status: str | None = None, q: str | None = None, mine: bool = False, user=Depends(Q), conn=Depends(get_db)):
    return inquiries.list_inquiries(conn, user, status or None, q, mine)


@router.post("/inquiries", status_code=201)
def create_inquiry(body: InquiryIn, user=Depends(Q), conn=Depends(get_db)):
    return inquiries.create(conn, body.given(), user)


@router.get("/inquiries/{inquiry_id}")
def get_inquiry(inquiry_id: int, user=Depends(Q), conn=Depends(get_db)):
    return inquiries.get_inquiry(conn, inquiry_id, user)


@router.patch("/inquiries/{inquiry_id}")
def update_inquiry(inquiry_id: int, body: InquiryIn, user=Depends(Q), conn=Depends(get_db)):
    return inquiries.update(conn, inquiry_id, body.given(), user)


@router.delete("/inquiries/{inquiry_id}", status_code=204)
def delete_inquiry(inquiry_id: int, user=Depends(Q), conn=Depends(get_db)):
    inquiries.delete(conn, inquiry_id, user)
    return Response(status_code=204)

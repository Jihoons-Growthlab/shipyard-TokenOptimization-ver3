from fastapi import APIRouter, Depends

from ..db import get_db
from ..deps import require
from ..schemas import DecisionIn
from ..services import approvals
from ..services.common import VIEW, WRITE

router = APIRouter(prefix="/api/approvals", tags=["approvals"])
R, W = require("M33", VIEW), require("M33", WRITE)


@router.get("/inbox")
def inbox(user=Depends(R), conn=Depends(get_db)):
    return approvals.inbox(conn, user)


@router.post("/{approval_id}/decision")
def decision(approval_id: int, body: DecisionIn, user=Depends(W), conn=Depends(get_db)):
    return approvals.decide(conn, approval_id, body.result, body.comment, user)


@router.get("/history")
def history(_=Depends(R), conn=Depends(get_db)):
    return approvals.history(conn)

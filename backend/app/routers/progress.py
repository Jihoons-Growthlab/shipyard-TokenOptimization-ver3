from fastapi import APIRouter, Depends

from ..db import get_db
from ..deps import require
from ..schemas import ProgressIn
from ..services import progress
from ..services.common import VIEW, WRITE

router = APIRouter(prefix="/api", tags=["progress"])
R, W = require("M22", VIEW), require("M22", WRITE)


@router.get("/progress-hulls")
def progress_hulls(_=Depends(R), conn=Depends(get_db)):
    return progress.progress_hulls(conn)


@router.get("/hulls/{hull_no}/progress-targets")
def targets(hull_no: str, include_done: bool = False, _=Depends(R), conn=Depends(get_db)):
    return progress.targets(conn, hull_no, include_done)


@router.get("/plans/{plan_id}/progress")
def plan_progress(plan_id: int, _=Depends(R), conn=Depends(get_db)):
    return progress.plan_progress(conn, plan_id)


@router.put("/plans/{plan_id}/progress/{work_dt}")
def save(plan_id: int, work_dt: str, body: ProgressIn, _=Depends(W), conn=Depends(get_db)):
    return progress.save(conn, plan_id, work_dt, body.model_dump())


@router.delete("/progress/{progress_id}")
def delete(progress_id: int, _=Depends(W), conn=Depends(get_db)):
    return progress.delete(conn, progress_id)

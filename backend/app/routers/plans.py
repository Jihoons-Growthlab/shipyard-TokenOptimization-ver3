from fastapi import APIRouter, Depends, Response

from ..db import get_db
from ..deps import current_user, require
from ..schemas import LinkDrawingIn, PlanIn, PredsIn, ScheduleIn
from ..services import plans
from ..services.common import VIEW, WRITE

router = APIRouter(prefix="/api", tags=["plans"])
R, W = require("M21", VIEW), require("M21", WRITE)


@router.get("/procs")
def procs(_=Depends(current_user), conn=Depends(get_db)):
    return plans.procs(conn)


@router.get("/plan-hulls")
def plan_hulls(_=Depends(R), conn=Depends(get_db)):
    return plans.plan_hulls(conn)


@router.get("/hulls/{hull_no}/plans")
def gantt(hull_no: str, block_id: int | None = None, _=Depends(R), conn=Depends(get_db)):
    return plans.gantt(conn, hull_no, block_id)


@router.post("/hulls/{hull_no}/plans", status_code=201)
def create_plan(hull_no: str, body: PlanIn, user=Depends(W), conn=Depends(get_db)):
    return plans.create_plan(conn, hull_no, body.model_dump(), user)


@router.get("/plans/{plan_id}")
def get_plan(plan_id: int, _=Depends(R), conn=Depends(get_db)):
    return plans.get_plan(conn, plan_id)


@router.patch("/plans/{plan_id}")
def update_plan(plan_id: int, body: PlanIn, _=Depends(W), conn=Depends(get_db)):
    data = body.given()
    data.setdefault("confirm_late_preds", False)
    return plans.update_plan(conn, plan_id, data)


@router.patch("/plans/{plan_id}/schedule")
def reschedule(plan_id: int, body: ScheduleIn, _=Depends(W), conn=Depends(get_db)):
    return plans.reschedule(conn, plan_id, body.plan_start_dt, body.plan_end_dt, body.confirm_late_preds)


@router.delete("/plans/{plan_id}", status_code=204)
def delete_plan(plan_id: int, _=Depends(W), conn=Depends(get_db)):
    plans.delete_plan(conn, plan_id)
    return Response(status_code=204)


@router.put("/plans/{plan_id}/predecessors")
def set_preds(plan_id: int, body: PredsIn, _=Depends(W), conn=Depends(get_db)):
    return plans.set_predecessors(conn, plan_id, body.pred_plan_ids, body.confirm_late_preds)


@router.get("/plans/{plan_id}/drawings")
def plan_drawings(plan_id: int, _=Depends(R), conn=Depends(get_db)):
    return plans.plan_drawings(conn, plan_id)


@router.post("/plans/{plan_id}/drawings", status_code=201)
def link_drawing(plan_id: int, body: LinkDrawingIn, _=Depends(W), conn=Depends(get_db)):
    plans.add_link(conn, body.drawing_id, plan_id, body.required)
    return plans.plan_drawings(conn, plan_id)


@router.delete("/plans/{plan_id}/drawings/{drawing_id}", status_code=204)
def unlink_drawing(plan_id: int, drawing_id: int, _=Depends(W), conn=Depends(get_db)):
    plans.remove_link(conn, drawing_id, plan_id)
    return Response(status_code=204)

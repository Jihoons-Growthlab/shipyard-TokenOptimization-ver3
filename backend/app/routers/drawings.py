from urllib.parse import quote

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import FileResponse

from ..db import get_db
from ..deps import require
from ..schemas import ApprovalRequestIn, DrawingIn, LinkPlanIn, RevisionIn
from ..services import drawings, plans
from ..services.common import VIEW, WRITE

router = APIRouter(prefix="/api/drawings", tags=["drawings"])
R, W = require("M31", VIEW), require("M31", WRITE)


@router.get("")
def list_drawings(hull_no: str | None = None, discipline: str | None = None, status: str | None = None,
                  q: str | None = None, _=Depends(R), conn=Depends(get_db)):
    return drawings.list_drawings(conn, hull_no, discipline, status, q)


@router.post("", status_code=201)
def create(body: DrawingIn, user=Depends(W), conn=Depends(get_db)):
    return drawings.create(conn, body.given(), user)


@router.get("/{drawing_id}")
def detail(drawing_id: int, _=Depends(R), conn=Depends(get_db)):
    return drawings.detail(conn, drawing_id)


@router.patch("/{drawing_id}")
def update(drawing_id: int, body: DrawingIn, user=Depends(W), conn=Depends(get_db)):
    return drawings.update(conn, drawing_id, body.given(), user)


@router.delete("/{drawing_id}", status_code=204)
def delete(drawing_id: int, _=Depends(W), conn=Depends(get_db)):
    drawings.delete(conn, drawing_id)
    return Response(status_code=204)


@router.get("/{drawing_id}/revisions")
def revisions(drawing_id: int, _=Depends(R), conn=Depends(get_db)):
    plans.get_drawing_row(conn, drawing_id)
    return drawings.revisions(conn, drawing_id)


@router.post("/{drawing_id}/revisions", status_code=201)
def new_revision(drawing_id: int, body: RevisionIn, user=Depends(W), conn=Depends(get_db)):
    return drawings.new_revision(conn, drawing_id, body.change_desc, user)


@router.post("/{drawing_id}/revisions/{rev_no}/pdf")
async def upload_pdf(drawing_id: int, rev_no: int, request: Request, filename: str | None = None,
                     _=Depends(W), conn=Depends(get_db)):
    # 권한 검사(의존성)가 본문 읽기보다 먼저 끝난다.
    return await drawings.upload_pdf(conn, drawing_id, rev_no, filename, request.headers.get("content-type"),
                                     request.headers.get("content-length"), request.stream())


@router.get("/{drawing_id}/revisions/{rev_no}/pdf")
def get_pdf(drawing_id: int, rev_no: int, _=Depends(R), conn=Depends(get_db)):
    path, name = drawings.pdf_path(conn, drawing_id, rev_no)
    return FileResponse(path, media_type="application/pdf", headers={
        "Content-Disposition": f"inline; filename*=UTF-8''{quote(name)}", "X-Content-Type-Options": "nosniff"})


@router.delete("/{drawing_id}/revisions/{rev_no}/pdf")
def delete_pdf(drawing_id: int, rev_no: int, _=Depends(W), conn=Depends(get_db)):
    return drawings.delete_pdf(conn, drawing_id, rev_no)


@router.post("/{drawing_id}/revisions/{rev_no}/request-approval")
def request_approval(drawing_id: int, rev_no: int, body: ApprovalRequestIn, _=Depends(W), conn=Depends(get_db)):
    return drawings.request_approval(conn, drawing_id, rev_no, body.reviewer_emp_no, body.approver_emp_no)


@router.post("/{drawing_id}/revisions/{rev_no}/issue")
def issue(drawing_id: int, rev_no: int, _=Depends(W), conn=Depends(get_db)):
    return drawings.issue(conn, drawing_id, rev_no)


@router.get("/{drawing_id}/plans")
def drawing_plans(drawing_id: int, _=Depends(R), conn=Depends(get_db)):
    return drawings.drawing_plans(conn, drawing_id)


@router.post("/{drawing_id}/plans", status_code=201)
def link_plan(drawing_id: int, body: LinkPlanIn, _=Depends(W), conn=Depends(get_db)):
    plans.add_link(conn, drawing_id, body.plan_id, body.required)
    return drawings.drawing_plans(conn, drawing_id)


@router.delete("/{drawing_id}/plans/{plan_id}", status_code=204)
def unlink_plan(drawing_id: int, plan_id: int, _=Depends(W), conn=Depends(get_db)):
    plans.remove_link(conn, drawing_id, plan_id)
    return Response(status_code=204)

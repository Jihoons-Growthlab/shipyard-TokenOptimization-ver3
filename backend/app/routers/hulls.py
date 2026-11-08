from fastapi import APIRouter, Depends, Response

from ..db import get_db
from ..deps import require
from ..schemas import BlockIn, HullIn, MilestonesIn
from ..services import hulls
from ..services.common import VIEW, WRITE

router = APIRouter(prefix="/api", tags=["hulls"])
R, W = require("M11", VIEW), require("M11", WRITE)


@router.get("/hulls")
def list_hulls(status: str | None = None, ship_type: str | None = None, q: str | None = None,
               _=Depends(R), conn=Depends(get_db)):
    return hulls.list_hulls(conn, status, ship_type, q)


@router.post("/hulls", status_code=201)
def create_hull(body: HullIn, user=Depends(W), conn=Depends(get_db)):
    return hulls.create_hull(conn, body.given(), user)


@router.get("/hulls/{hull_no}")
def get_hull(hull_no: str, _=Depends(R), conn=Depends(get_db)):
    return hulls.get_hull(conn, hull_no)


@router.patch("/hulls/{hull_no}")
def update_hull(hull_no: str, body: HullIn, user=Depends(W), conn=Depends(get_db)):
    return hulls.update_hull(conn, hull_no, body.given(), user)


@router.delete("/hulls/{hull_no}", status_code=204)
def delete_hull(hull_no: str, _=Depends(W), conn=Depends(get_db)):
    hulls.delete_hull(conn, hull_no)
    return Response(status_code=204)


@router.get("/hulls/{hull_no}/milestones")
def milestones(hull_no: str, _=Depends(R), conn=Depends(get_db)):
    return hulls.milestones(conn, hull_no)


@router.put("/hulls/{hull_no}/milestones")
def save_milestones(hull_no: str, body: MilestonesIn, _=Depends(W), conn=Depends(get_db)):
    return hulls.save_milestones(conn, hull_no, [i.model_dump() for i in body.items])


@router.get("/hulls/{hull_no}/blocks")
def blocks(hull_no: str, _=Depends(R), conn=Depends(get_db)):
    return hulls.blocks(conn, hull_no)


@router.post("/hulls/{hull_no}/blocks", status_code=201)
def create_block(hull_no: str, body: BlockIn, _=Depends(W), conn=Depends(get_db)):
    return hulls.create_block(conn, hull_no, body.given())


@router.delete("/blocks/{block_id}", status_code=204)
def delete_block(block_id: int, _=Depends(W), conn=Depends(get_db)):
    hulls.delete_block(conn, block_id)
    return Response(status_code=204)


@router.get("/hulls/{hull_no}/summary")
def summary(hull_no: str, _=Depends(R), conn=Depends(get_db)):
    return hulls.summary(conn, hull_no)

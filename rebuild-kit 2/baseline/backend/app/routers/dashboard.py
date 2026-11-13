from fastapi import APIRouter, Depends

from ..db import get_db
from ..deps import require
from ..services import dashboard

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/summary")
def summary(_=Depends(require("M00")), conn=Depends(get_db)):
    return dashboard.summary(conn)

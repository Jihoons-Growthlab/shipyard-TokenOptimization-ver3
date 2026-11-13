from fastapi import APIRouter, Depends, Response

from ..db import get_db
from ..deps import current_user
from ..schemas import MenuAccessIn
from ..services import common, shell

router = APIRouter(prefix="/api", tags=["shell"])


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/me/menu")
def my_menu(user=Depends(current_user), conn=Depends(get_db)):
    return shell.my_menu(conn, user["emp_no"])


@router.post("/me/menu-access", status_code=204)
def menu_access(body: MenuAccessIn, user=Depends(current_user), conn=Depends(get_db)):
    shell.log_menu_access(conn, user, body.menu_id)
    return Response(status_code=204)


@router.get("/weather")
def weather(region: str | None = None, _=Depends(current_user)):
    return shell.weather(region)


@router.get("/codes")
def codes(_=Depends(current_user), conn=Depends(get_db)):
    return common.codes(conn)


@router.get("/users/options")
def user_options(_=Depends(current_user), conn=Depends(get_db)):
    return common.user_options(conn)

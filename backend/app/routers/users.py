from fastapi import APIRouter, Depends, Response

from ..db import get_db
from ..deps import require
from ..schemas import ApproveIn, UserIn, UserMenusIn
from ..services import users
from ..services.common import ADMIN

router = APIRouter(prefix="/api", tags=["users"])
A = require("M91", ADMIN)


@router.get("/users")
def list_users(status: str | None = None, q: str | None = None, _=Depends(A), conn=Depends(get_db)):
    return users.list_users(conn, status, q)


@router.post("/users", status_code=201)
def create_user(body: UserIn, _=Depends(A), conn=Depends(get_db)):
    return users.create_user(conn, body.given())


@router.get("/users/{emp_no}")
def get_user(emp_no: str, _=Depends(A), conn=Depends(get_db)):
    return users.get_user(conn, emp_no)


@router.patch("/users/{emp_no}")
def update_user(emp_no: str, body: UserIn, _=Depends(A), conn=Depends(get_db)):
    return users.update_user(conn, emp_no, body.given())


@router.delete("/users/{emp_no}", status_code=204)
def delete_user(emp_no: str, actor=Depends(A), conn=Depends(get_db)):
    users.delete_user(conn, emp_no, actor)
    return Response(status_code=204)


@router.get("/users/{emp_no}/menus")
def user_menus(emp_no: str, _=Depends(A), conn=Depends(get_db)):
    return users.user_menus(conn, emp_no)


@router.put("/users/{emp_no}/menus")
def set_user_menus(emp_no: str, body: UserMenusIn, actor=Depends(A), conn=Depends(get_db)):
    return users.set_user_menus(conn, emp_no, [m.model_dump() for m in body.menus], actor)


@router.post("/users/{emp_no}/approve")
def approve(emp_no: str, body: ApproveIn, _=Depends(A), conn=Depends(get_db)):
    return users.approve(conn, emp_no, body.groups)


@router.post("/users/{emp_no}/reject")
def reject(emp_no: str, _=Depends(A), conn=Depends(get_db)):
    return users.reject(conn, emp_no)


@router.get("/auth-groups")
def auth_groups(_=Depends(A), conn=Depends(get_db)):
    return users.auth_groups(conn)

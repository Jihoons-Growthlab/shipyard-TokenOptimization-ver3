from fastapi import APIRouter, Depends, Request, Response

from ..db import get_db
from ..deps import current_user, token_payload
from ..schemas import LoginIn, MemberIn, OtpIn
from ..services import auth

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _ip(request: Request):
    return request.client.host if request.client else None


@router.post("/login")
def login(body: LoginIn, request: Request, conn=Depends(get_db)):
    return auth.login(conn, body.emp_no, body.password, _ip(request))


@router.post("/otp/verify")
def otp_verify(body: OtpIn, request: Request, payload=Depends(token_payload), conn=Depends(get_db)):
    return auth.verify_otp(conn, payload, body.code, _ip(request))


@router.post("/register", status_code=201)
def register(body: MemberIn, conn=Depends(get_db)):
    return auth.register(conn, body.model_dump())


@router.post("/logout", status_code=204)
def logout(user=Depends(current_user), conn=Depends(get_db)):
    auth.logout(conn, user)
    return Response(status_code=204)


@router.get("/me")
def me(user=Depends(current_user), conn=Depends(get_db)):
    return auth.me(conn, user)

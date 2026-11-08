"""FastAPI 진입점. 라우터(입출력·권한) → 서비스(규칙) → DB."""
from fastapi import FastAPI

from . import errors
from .routers import approvals, auth, dashboard, drawings, hulls, plans, progress, shell, users

app = FastAPI(title="SWP Shipyard API", version="3.0")
errors.install(app)

for _r in (shell, auth, hulls, plans, progress, drawings, approvals, users, dashboard):
    app.include_router(_r.router)

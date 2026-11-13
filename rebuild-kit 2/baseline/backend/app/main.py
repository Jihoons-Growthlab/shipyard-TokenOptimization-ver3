"""FastAPI 진입점. 라우터(입출력·권한) → 서비스(규칙) → DB."""
import time

from fastapi import FastAPI, Request
from starlette.concurrency import run_in_threadpool

from . import errors
from .services.usage import record
from .routers import approvals, auth, chat, chat_report, dashboard, drawings, hulls, plans, progress, shell, usage, users

app = FastAPI(title="SWP Shipyard API", version="3.0")
errors.install(app)

for _r in (shell, auth, hulls, plans, progress, drawings, approvals, users, dashboard, chat, usage, chat_report):
    app.include_router(_r.router)


@app.middleware("http")
async def log_api_calls(request: Request, call_next):
    """사용 로그(명세 외 요청 기능): API 호출마다 사용자·경로 템플릿·상태·소요시간을 남긴다."""
    t0 = time.perf_counter()
    response = await call_next(request)
    route = request.scope.get("route")
    path = getattr(route, "path", None) or request.url.path
    await run_in_threadpool(record, getattr(request.state, "emp_no", None), request.method, path, response.status_code,
                            int((time.perf_counter() - t0) * 1000))
    return response

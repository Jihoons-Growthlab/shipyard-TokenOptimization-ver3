"""챗봇 보고서 작성·다운로드(명세 외 요청 기능). 생성은 MCP 서버의 build_report 도구가 한다."""
from typing import Literal, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from ..db import get_db, rows
from ..deps import current_user
from ..errors import ApiError
from ..services import reports
from ..services.common import VIEW, menu_level
from ..services.hull_chat import call_tool

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ReportIn(BaseModel):
    format: Literal["pdf", "xlsx"]
    hull_no: Optional[str] = Field(default=None, max_length=20)


@router.get("/report/options")
def report_options(user=Depends(current_user), conn=Depends(get_db)):
    hulls = rows(conn, "SELECT HullNo hull_no, HullNm hull_nm FROM TB_MST_Hull WHERE UseYN=1 ORDER BY HullNo") \
        if menu_level(conn, user["emp_no"], "M11") >= VIEW else []
    return {"hulls": hulls, "formats": [{"code": "pdf", "name": "PDF"}, {"code": "xlsx", "name": "Excel"}]}


@router.post("/report", status_code=201)
def create_report(body: ReportIn, user=Depends(current_user)):
    data = call_tool(user["emp_no"], "build_report", body.model_dump())
    if "error" in data:
        raise ApiError(data.get("status", 400), "REPORT_ERROR", data["error"])
    data["download_url"] = f"/api/chat/reports/{data['report_id']}?format={data['format']}"
    return data


@router.get("/reports/{report_id}")
def download_report(report_id: str, format: Literal["pdf", "xlsx"] = "pdf", user=Depends(current_user)):
    path = reports.report_file(user["emp_no"], report_id, format)
    return FileResponse(path, media_type=reports.FORMATS[format], filename=f"report-{report_id[:8]}.{format}")

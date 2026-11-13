"""Local MCP server using newline-delimited JSON-RPC over stdio."""
import json
import sys
from uuid import UUID
from contextlib import closing

from .db import connect
from .services.common import VIEW, WRITE, menu_level
from .services.hulls import list_hulls
from .services import drawings, inquiries, progress

PROTOCOL = "2025-03-26"
TOOL = {
    "name": "search_hulls",
    "description": "Search registered shipyard hulls by number or name.",
    "inputSchema": {
        "type": "object",
        "properties": {"query": {"type": "string", "maxLength": 100}},
        "additionalProperties": False,
    },
}
FEEDBACK_TOOL = {
    "name": "submit_feedback",
    "description": "Record an explicitly submitted suggestion or inquiry.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "kind": {"enum": ["suggestion", "inquiry"]},
            "content": {"type": "string", "minLength": 1, "maxLength": 2000},
            "request_id": {"type": "string", "format": "uuid"},
        },
        "required": ["kind", "content", "request_id"],
    },
}

REPORT_TOOL = {
    "name": "build_report",
    "description": "Build a hull/plan/drawing status report as PDF or Excel for download.",
    "inputSchema": {
        "type": "object",
        "properties": {"format": {"enum": ["pdf", "xlsx"]}, "hull_no": {"type": ["string", "null"], "maxLength": 20}},
        "required": ["format"],
        "additionalProperties": False,
    },
}


def build_report(emp_no, arguments):
    """보고서 작성(명세 외 요청 기능). 오류 메시지는 그대로 돌려줘 챗봇이 안내한다."""
    from .errors import ApiError
    from .services import reports
    fmt, hull_no = arguments.get("format"), arguments.get("hull_no") or None
    if fmt not in reports.FORMATS or (hull_no is not None and (not isinstance(hull_no, str) or len(hull_no) > 20)):
        raise ValueError("Invalid report arguments")
    with closing(connect()) as conn:
        try:
            return reports.build(conn, emp_no, hull_no, fmt)
        except ApiError as exc:
            return {"error": exc.message, "status": exc.status}


CATALOGS = {
    "list_drawings": ("M31", drawings.list_drawings,
                      ("drawing_id", "drawing_no", "drawing_nm", "hull_no", "dwg_status")),
    "list_progress_hulls": ("M22", lambda conn: progress.progress_hulls(conn)["hulls"],
                            ("hull_no", "hull_nm")),
}
CATALOG_TOOLS = [
    {"name": name, "description": description, "inputSchema": {"type": "object", "properties": {}}}
    for name, description in [("list_drawings", "List registered drawings"),
                              ("list_progress_hulls", "List hulls with construction plans")]
]
FIELDS = ("hull_no", "hull_nm", "hull_status", "progress", "delay_count", "delivery_dt")


def submit_feedback(emp_no, arguments):
    kind = arguments.get("kind")
    content = arguments.get("content")
    if kind not in ("suggestion", "inquiry") or not isinstance(content, str) or not 1 <= len(content.strip()) <= 2000:
        raise ValueError("Invalid feedback")
    request_id = str(UUID(arguments["request_id"]))
    with closing(connect()) as conn:
        if menu_level(conn, emp_no, inquiries.MENU) < WRITE:
            return {"forbidden": True}
        inquiry_id = inquiries.create_from_chat(conn, emp_no, request_id, kind, content.strip())
    return {"receipt": f"FB-{inquiry_id:06d}", "inquiry_id": inquiry_id}


def dispatch(message, emp_no):
    method = message.get("method")
    if method == "initialize":
        return {"protocolVersion": PROTOCOL, "capabilities": {"tools": {}},
                "serverInfo": {"name": "shipyard-hulls", "version": "1.0"}}
    if method == "tools/list":
        return {"tools": [TOOL, *CATALOG_TOOLS, FEEDBACK_TOOL, REPORT_TOOL]}
    if method == "tools/call":
        params = message.get("params", {})
        name = params.get("name")
        if name == FEEDBACK_TOOL["name"]:
            data = submit_feedback(emp_no, params.get("arguments", {}))
            return {"content": [{"type": "text", "text": json.dumps(data)}]}
        if name == REPORT_TOOL["name"]:
            data = build_report(emp_no, params.get("arguments", {}))
            return {"content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False)}]}
        if name in CATALOGS:
            menu, load, fields = CATALOGS[name]
            with closing(connect()) as conn:
                conn.execute("PRAGMA query_only=ON")
                data = {"forbidden": True}
                if menu_level(conn, emp_no, menu) >= VIEW:
                    items = load(conn)
                    data = {"items": [{field: item[field] for field in fields} for item in items]}
            return {"content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False)}]}
        if name != TOOL["name"]:
            raise ValueError("Unknown tool")
        query = params.get("arguments", {}).get("query", "")
        if not isinstance(query, str) or len(query) > 100:
            raise ValueError("Invalid query")
        with closing(connect()) as conn:
            conn.execute("PRAGMA query_only=ON")
            if menu_level(conn, emp_no, "M11") < VIEW:
                data = {"forbidden": True}
            else:
                hulls = list_hulls(conn, q=query)
                data = {"hulls": [{field: hull[field] for field in FIELDS} for hull in hulls[:20]],
                        "total": len(hulls)}
        return {"content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False)}]}
    raise ValueError("Unknown method")


def main():
    emp_no = sys.argv[1]
    for line in sys.stdin:
        message = json.loads(line)
        if "id" not in message:
            continue
        response = {"jsonrpc": "2.0", "id": message["id"]}
        try:
            response["result"] = dispatch(message, emp_no)
        except ValueError as exc:
            response["error"] = {"code": -32602, "message": str(exc)}
        print(json.dumps(response, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()

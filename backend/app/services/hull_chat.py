"""Route hull lookup prompts to the local MCP server."""
import json
import re
import subprocess
import sys
from pathlib import Path

from ..errors import ApiError, forbidden

LOOKUP = re.compile(r"호선\s*(?:의\s*)?(?:상세|정보|목록|현황|상태|진척|조회|선택|검색)|호선.*알려|\bSN[\s-]*\d+",
                    re.IGNORECASE)
QUERY = re.compile(r"^(?:실제\s*)?(.+?)\s*호선", re.IGNORECASE)


def call_tool(emp_no, name, arguments):
    def message(method, params, request_id=None):
        data = {"jsonrpc": "2.0", "method": method, "params": params}
        if request_id is not None:
            data["id"] = request_id
        return json.dumps(data, ensure_ascii=False)

    requests = [
        message("initialize", {"protocolVersion": "2025-03-26", "capabilities": {},
                               "clientInfo": {"name": "shipyard-chat", "version": "1.0"}}, 1),
        message("notifications/initialized", {}),
        message("tools/call", {"name": name, "arguments": arguments}, 2),
    ]
    try:
        process = subprocess.run([sys.executable, "-m", "app.hull_mcp", emp_no],
                                 cwd=Path(__file__).resolve().parents[2],
                                 input="\n".join(requests) + "\n", text=True, encoding="utf-8",
                                 capture_output=True, check=True, timeout=10)
        initialized, reply = map(json.loads, process.stdout.splitlines())
        if initialized["result"]["protocolVersion"] != "2025-03-26" or reply["id"] != 2:
            raise ValueError("Invalid MCP response")
        return json.loads(reply["result"]["content"][0]["text"])
    except (subprocess.SubprocessError, OSError, ValueError, KeyError, IndexError) as exc:
        raise ApiError(502, "HULL_MCP_ERROR", "호선 조회 서버에 연결하지 못했습니다.") from exc


def search(emp_no, query):
    return call_tool(emp_no, "search_hulls", {"query": query})


def hull_reply(question, emp_no):
    if re.search(r"공정\s*실적|실적\s*(?:정보|알려|조회)", question):
        result = call_tool(emp_no, "list_progress_hulls", {})
        if result.get("forbidden"):
            raise forbidden("M22")
        return {"answer": "어떤 공정의 실적을 볼까요? 먼저 호선을 선택해 주세요."
                if result["items"] else "공정이 등록된 호선이 없습니다.",
                "choice_type": "progress-hull", "choices": result["items"]}
    if re.search(r"도면.*(?:정보|알려|목록|조회|선택|보여|검색)", question):
        result = call_tool(emp_no, "list_drawings", {})
        if result.get("forbidden"):
            raise forbidden("M31")
        return {"answer": "상세 정보를 볼 도면을 선택해 주세요."
                if result["items"] else "등록된 도면이 없습니다.",
                "choice_type": "drawing", "choices": result["items"]}
    if not LOOKUP.search(question):
        return None
    match = QUERY.search(question)
    serial = re.search(r"\bSN[\s-]*\d+\b", question, re.IGNORECASE)
    number_after_hull = re.search(r"호선\s+([0-9][0-9A-Za-z-]*)\b", question)
    query = (serial[0] if serial else number_after_hull[1] if number_after_hull
             else match[1].strip() if match else "")[:100]
    result = search(emp_no, query)
    if query.casefold() == "sn" and not result.get("hulls") and not result.get("forbidden"):
        result = search(emp_no, "")
        answer = "‘SN’으로 등록된 호선을 찾지 못했습니다. 등록된 호선 중에서 선택해 주세요."
    elif not result.get("hulls"):
        answer = "일치하는 호선이 없습니다. 호선 번호나 이름을 확인해 주세요."
    else:
        answer = "상세 정보를 볼 호선을 선택해 주세요."
    if result.get("forbidden"):
        raise forbidden("M11")
    if result["total"] > len(result["hulls"]):
        answer += " 처음 20척을 표시합니다. 호선 번호나 이름으로 범위를 좁힐 수 있습니다."
    return {"answer": answer, "hulls": result["hulls"]}

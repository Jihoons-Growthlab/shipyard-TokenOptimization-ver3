"""챗봇 보고서(명세 외 요청 기능): MCP build_report 도구로 PDF·Excel을 만들고 만든 사람만 내려받는다."""
import io


def test_report_pdf_and_excel_via_mcp(client, auth):
    h = auth("park.pm")
    opts = client.get("/api/chat/report/options", headers=h).json()
    assert opts["hulls"][0]["hull_no"] == "8001" and [f["code"] for f in opts["formats"]] == ["pdf", "xlsx"]

    r = client.post("/api/chat/report", json={"format": "pdf", "hull_no": "8001"}, headers=h)
    assert r.status_code == 201, r.text
    rep = r.json()
    assert rep["title"] == "8001 호선 현황 보고서" and rep["filename"].endswith(".pdf") and rep["summary"]["plans"] > 0
    pdf = client.get(rep["download_url"], headers=h)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF") and pdf.headers["content-type"] == "application/pdf"
    # 다른 사람은 내려받을 수 없다.
    assert client.get(rep["download_url"], headers=auth("choi.qa")).status_code == 404

    x = client.post("/api/chat/report", json={"format": "xlsx"}, headers=h).json()
    assert x["title"] == "전체 호선 현황 보고서"
    data = client.get(x["download_url"], headers=h).content
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(data))
    assert wb.sheetnames == ["요약", "호선", "공정", "도면"]
    assert wb["호선"]["A1"].value == "호선번호" and wb["호선"].max_row == 6

    assert client.post("/api/chat/report", json={"format": "doc"}, headers=h).status_code == 422
    r = client.post("/api/chat/report", json={"format": "pdf", "hull_no": "9999"}, headers=h)
    assert r.status_code == 404
    assert client.get("/api/chat/reports/../../etc?format=pdf", headers=h).status_code == 404

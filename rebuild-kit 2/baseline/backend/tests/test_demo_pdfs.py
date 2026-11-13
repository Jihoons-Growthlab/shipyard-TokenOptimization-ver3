"""예시 도면 PDF(명세 외 요청 기능): 파일 없는 리비전에만 붙고, 다시 실행하면 아무것도 하지 않는다."""
from app.db import scalar
from app.demo_pdfs import attach_demo_pdfs


def test_demo_pdfs_attach_once(client, auth, db):
    missing = scalar(db, "SELECT COUNT(*) FROM TB_DWG_Revision WHERE FileId IS NULL")
    assert attach_demo_pdfs(db) == missing > 0
    assert attach_demo_pdfs(db) == 0
    assert scalar(db, "SELECT COUNT(*) FROM TB_DWG_Revision WHERE FileId IS NULL") == 0
    h = auth("choi.qa")
    did, rev = db.execute("SELECT DrawingId, RevNo FROM TB_DWG_Revision WHERE RevStatus='ISSUED' LIMIT 1").fetchone()
    r = client.get(f"/api/drawings/{did}/revisions/{rev}/pdf", headers=h)
    assert r.status_code == 200 and r.content.startswith(b"%PDF-") and r.content.rstrip().endswith(b"%%EOF")

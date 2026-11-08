"""테스트 공용 헬퍼."""
from app.db import connect
from app.services.rules import recalc_hull


def make_drawing(db, hull_no, drawing_no, rev_status="DRAFT", dwg_status=None, block_id=None):
    cur = db.execute("INSERT INTO TB_DWG_Drawing(DrawingNo, DrawingNm, HullNo, BlockId, DwgStatus, CurrentRevNo) "
                     "VALUES (?,?,?,?,?,0)", (drawing_no, drawing_no + " 도면", hull_no, block_id, dwg_status or rev_status))
    db.execute("INSERT INTO TB_DWG_Revision(DrawingId, RevNo, RevStatus, ChangeDesc, IssueDt) VALUES (?,0,?,?,?)",
               (cur.lastrowid, rev_status, "최초 작성", "2026-10-01" if rev_status == "ISSUED" else None))
    return cur.lastrowid


def recalc(hull_no):
    conn = connect()
    conn.execute("BEGIN IMMEDIATE")
    recalc_hull(conn, hull_no)
    conn.execute("COMMIT")
    conn.close()


def new_plan(client, h, hull_no, **kw):
    body = {"proc_cd": "CUT", "plan_start_dt": "2026-11-01", "plan_end_dt": "2026-11-14", **kw}
    r = client.post(f"/api/hulls/{hull_no}/plans", json=body, headers=h)
    assert r.status_code == 201, r.text
    return r.json()


def orphan_counts(db):
    checks = {
        "milestone": "SELECT COUNT(*) FROM TB_MST_HullMilestone m WHERE NOT EXISTS (SELECT 1 FROM TB_MST_Hull h WHERE h.HullNo=m.HullNo)",
        "block": "SELECT COUNT(*) FROM TB_MST_Block b WHERE NOT EXISTS (SELECT 1 FROM TB_MST_Hull h WHERE h.HullNo=b.HullNo)",
        "plan": "SELECT COUNT(*) FROM TB_PRC_Plan p WHERE NOT EXISTS (SELECT 1 FROM TB_MST_Hull h WHERE h.HullNo=p.HullNo)",
        "dep": "SELECT COUNT(*) FROM TB_PRC_PlanDep d WHERE NOT EXISTS (SELECT 1 FROM TB_PRC_Plan p WHERE p.PlanId=d.PlanId) "
               "OR NOT EXISTS (SELECT 1 FROM TB_PRC_Plan p WHERE p.PlanId=d.PredPlanId)",
        "progress": "SELECT COUNT(*) FROM TB_PRC_Progress g WHERE NOT EXISTS (SELECT 1 FROM TB_PRC_Plan p WHERE p.PlanId=g.PlanId)",
        "drawing": "SELECT COUNT(*) FROM TB_DWG_Drawing d WHERE NOT EXISTS (SELECT 1 FROM TB_MST_Hull h WHERE h.HullNo=d.HullNo)",
        "revision": "SELECT COUNT(*) FROM TB_DWG_Revision r WHERE NOT EXISTS (SELECT 1 FROM TB_DWG_Drawing d WHERE d.DrawingId=r.DrawingId)",
        "approval": "SELECT COUNT(*) FROM TB_DWG_Approval a WHERE NOT EXISTS (SELECT 1 FROM TB_DWG_Revision r WHERE r.DrawingId=a.DrawingId AND r.RevNo=a.RevNo)",
        "link": "SELECT COUNT(*) FROM TB_DWG_PlanLink l WHERE NOT EXISTS (SELECT 1 FROM TB_DWG_Drawing d WHERE d.DrawingId=l.DrawingId) "
                "OR NOT EXISTS (SELECT 1 FROM TB_PRC_Plan p WHERE p.PlanId=l.PlanId)",
    }
    return {k: db.execute(sql).fetchone()[0] for k, sql in checks.items()}

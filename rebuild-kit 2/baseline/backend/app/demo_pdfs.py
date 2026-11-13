"""개발·시연용 예시 도면 PDF(명세 외 요청 기능). 파일이 없는 리비전마다 도면 형태의 PDF를 만들어 붙인다.

외부 라이브러리 없이 PDF를 직접 쓴다. 기본 폰트(Helvetica)는 한글을 못 그리므로 도면 안 글자는 영문·숫자만 쓴다.
반복 실행해도 파일이 이미 있는 리비전은 건드리지 않는다.
"""
import secrets

from .db import rows, tx
from .services.rules import file_path

W, H = 1191, 842  # A3 가로(pt)
DISC = {"HULL": "HULL STRUCTURE", "PIPE": "PIPING ARRANGEMENT", "ELEC": "ELECTRICAL WIRING",
        "MACH": "MACHINERY ARRANGEMENT", "OUTFIT": "OUTFITTING ARRANGEMENT"}
STAMP = {"DRAFT": "DRAFT", "REVIEW": "FOR REVIEW", "APPROVED": "APPROVED - NOT ISSUED", "OBSOLETE": "SUPERSEDED"}


def _esc(s: str) -> str:
    s = "".join(c if 32 <= ord(c) < 127 else "?" for c in str(s))
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _text(x, y, size, s, font="F1"):
    return f"BT /{font} {size} Tf {x} {y} Td ({_esc(s)}) Tj ET"


def _frame() -> list[str]:
    return ["0 0 0 RG 2 w 20 20 m 1171 20 l 1171 822 l 20 822 l h S", "0.8 w 34 34 m 1157 34 l 1157 808 l 34 808 l h S"]


def _title_block(d: dict, rev: dict) -> list[str]:
    x, y, w, h = 757, 34, 400, 160
    out = ["0.8 w", f"{x} {y} {w} {h} re S"]
    for yy in (y + 40, y + 80, y + 120):
        out.append(f"{x} {yy} m {x + w} {yy} l S")
    out.append(f"{x + 200} {y} m {x + 200} {y + 80} l S")
    cells = [(x + 8, y + 146, "PROJECT", f"HULL {d['HullNo']}"),
             (x + 8, y + 106, "DRAWING TITLE", f"{DISC.get(d['Discipline'], d['Discipline'])} - BLOCK {d['BlockCd'] or 'GENERAL'}"),
             (x + 8, y + 66, "DRAWING NO", d["DrawingNo"]), (x + 208, y + 66, "REV / STATUS", f"REV {rev['RevNo']}  {rev['RevStatus']}"),
             (x + 8, y + 26, "DESIGNED BY", d["DesignerEmpNo"] or "-"), (x + 208, y + 26, "DATE", rev["IssueDt"] or rev["CreateDt"] or "-")]
    for cx, cy, label, val in cells:
        out += [_text(cx, cy, 7, label), _text(cx, cy - 15, 11, val, "F2")]
    out.append(_text(x - 330, 44, 8, "SWP SHIPYARD  |  SAMPLE DRAWING FOR DEMONSTRATION - NOT FOR CONSTRUCTION"))
    return out


def _rev_table(revs: list[dict], upto: int) -> list[str]:
    x, top = 857, 808
    out = ["0.6 w", f"{x} {top - 18} m 1157 {top - 18} l S", _text(x + 6, top - 13, 8, "REV   DATE         DESCRIPTION", "F2")]
    for i, r in enumerate([r for r in revs if r["RevNo"] <= upto][-5:]):
        y = top - 32 - i * 14
        out.append(_text(x + 6, y, 8, f"{r['RevNo']:<5} {(r['IssueDt'] or r['CreateDt'] or '-')[:10]:<12} {r['RevStatus']}"))
    out.append(f"{x} {top} m {x} {top - 110} l {x} {top - 110} m 1157 {top - 110} l S")
    return out


def _hull(seed: int) -> list[str]:
    out = ["1.6 w", "120 300 m 860 300 l 900 300 940 380 960 520 c 120 520 l h S",  # 선체 측면
           "0.5 w [4 3] 0 d"]
    out += [f"{x} 300 m {x} 520 l S" for x in range(160, 860, 40)]  # 프레임선
    out += ["[] 0 d 1 w", "120 410 m 900 410 l S", "120 470 m 935 470 l S"]  # 갑판
    bx = 200 + (seed % 5) * 110
    out += ["0.85 0.2 0.2 RG 2.2 w", f"{bx} 300 {160} {220} re S", "0 0 0 RG",
            _text(bx + 40, 530, 10, "THIS BLOCK", "F2"), _text(120, 540, 9, "PROFILE  (FR. SPACING 800)")]
    out += ["1 w", "120 100 m 640 100 l 690 140 l 640 180 l 120 180 l h S", _text(120, 190, 9, "PLAN VIEW")]
    out += [f"{x} 100 m {x} 180 l S" for x in range(200, 640, 80)]
    return out


def _pipe(seed: int) -> list[str]:
    out = ["2.4 w"]
    ys = [620, 520, 420, 320]
    for i, y in enumerate(ys):
        out.append(f"100 {y} m {600 + (seed * 37 + i * 60) % 150} {y} l S")
    out += ["2.4 w", "300 620 m 300 320 l S", "520 520 m 520 240 l 600 240 l S"]
    for x, y in [(200, 620), (420, 520), (360, 420), (560, 240)]:  # 밸브
        out.append(f"1.2 w {x - 10} {y - 8} m {x + 10} {y + 8} l {x + 10} {y - 8} l {x - 10} {y + 8} l h S")
    out += ["1.4 w", "600 240 m 600 262 618 280 640 280 c 662 280 680 262 680 240 c 680 218 662 200 640 200 c "
            "618 200 600 218 600 240 c S", _text(622, 236, 9, "PUMP", "F2"), _text(100, 640, 9, "P&ID - SEA WATER / FUEL OIL LINES")]
    return out


def _elec(seed: int) -> list[str]:
    out = ["1.2 w"]
    panels = [(100, 560), (100, 380), (100, 200)]
    for i, (x, y) in enumerate(panels):
        out += [f"{x} {y} 140 90 re S", _text(x + 12, y + 40, 10, f"PANEL {chr(65 + i)}{seed % 9 + 1}", "F2")]
        for j in range(4):
            ty = y + 15 + j * 20
            out.append(f"{x + 140} {ty} m {420 + j * 90} {ty} l {420 + j * 90} {ty + 140 - i * 30} l S")
    for j in range(4):  # 부하(원)
        cx, cy = 420 + j * 90, 700
        out.append(f"{cx - 14} {cy} m {cx - 14} {cy + 8} {cx - 8} {cy + 14} {cx} {cy + 14} c {cx + 8} {cy + 14} {cx + 14} "
                   f"{cy + 8} {cx + 14} {cy} c {cx + 14} {cy - 8} {cx + 8} {cy - 14} {cx} {cy - 14} c {cx - 8} {cy - 14} "
                   f"{cx - 14} {cy - 8} {cx - 14} {cy} c S")
    out.append(_text(100, 680, 9, "SINGLE LINE DIAGRAM - 440V / 220V"))
    return out


def _generic(seed: int) -> list[str]:
    out = ["1.2 w"]
    for i in range(6):
        x, y = 120 + (i % 3) * 230, 200 + (i // 3) * 220
        out += [f"{x} {y} 180 150 re S", f"{x} {y} m {x + 180} {y + 150} l S", _text(x + 10, y + 160, 9, f"ITEM {seed % 7 + i + 1}")]
    return out


SKETCH = {"HULL": _hull, "PIPE": _pipe, "ELEC": _elec}


def drawing_pdf(d: dict, rev: dict, revs: list[dict]) -> bytes:
    ops = ["q"] + _frame() + _title_block(d, rev) + _rev_table(revs, rev["RevNo"])
    ops += SKETCH.get(d["Discipline"], _generic)(d["DrawingId"] + rev["RevNo"])
    ops.append(_text(60, 770, 20, d["DrawingNo"], "F2"))
    ops.append(_text(60, 748, 11, DISC.get(d["Discipline"], d["Discipline"])))
    if rev["RevStatus"] in STAMP:
        ops += ["0.85 0.2 0.2 RG 0.85 0.2 0.2 rg 2 w", "560 700 260 46 re S",
                _text(575, 715, 18, STAMP[rev["RevStatus"]], "F2"), "0 0 0 RG 0 0 0 rg"]
    ops.append("Q")
    content = "\n".join(ops).encode("latin-1")
    objs = [b"<</Type/Catalog/Pages 2 0 R>>", b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
            f"<</Type/Page/Parent 2 0 R/MediaBox[0 0 {W} {H}]/Contents 4 0 R"
            "/Resources<</Font<</F1 5 0 R/F2 6 0 R>>>>>>".encode(),
            b"<</Length %d>>stream\n" % len(content) + content + b"\nendstream",
            b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>", b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica-Bold>>",
            f"<</Title({_esc(d['DrawingNo'])} Rev{rev['RevNo']})/Subject({_esc(DISC.get(d['Discipline'], ''))})"
            "/Producer(SWP Shipyard sample)>>".encode()]
    out, offsets = bytearray(b"%PDF-1.4\n"), []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    out += b"".join(b"%010d 00000 n \n" % off for off in offsets)
    out += b"trailer\n<</Size %d/Root 1 0 R/Info %d 0 R>>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, len(objs), xref)
    return bytes(out)


def attach_demo_pdfs(conn) -> int:
    """파일 없는 리비전에 예시 PDF를 붙이고 붙인 수를 돌려준다."""
    drawings = {r["DrawingId"]: r for r in rows(
        conn, "SELECT d.DrawingId, d.DrawingNo, d.HullNo, d.Discipline, d.DesignerEmpNo, b.BlockCd "
              "FROM TB_DWG_Drawing d LEFT JOIN TB_MST_Block b ON b.BlockId=d.BlockId")}
    revs: dict[int, list[dict]] = {}
    for r in rows(conn, "SELECT DrawingId, RevNo, RevStatus, IssueDt, CreateDt, FileId FROM TB_DWG_Revision ORDER BY DrawingId, RevNo"):
        revs.setdefault(r["DrawingId"], []).append(r)
    written = []
    try:
        for did, rs in revs.items():
            for r in rs:
                if r["FileId"] or did not in drawings:
                    continue
                fid = secrets.token_hex(16)
                path = file_path(fid)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(drawing_pdf(drawings[did], r, rs))
                written.append((fid, f"{drawings[did]['DrawingNo']}_Rev{r['RevNo']}.pdf", did, r["RevNo"], path))
        with tx(conn):
            conn.executemany("UPDATE TB_DWG_Revision SET FileId=?, FileNm=? WHERE DrawingId=? AND RevNo=? AND FileId IS NULL",
                             [w[:4] for w in written])
    except BaseException:
        for w in written:
            w[4].unlink(missing_ok=True)
        raise
    return len(written)

"""기능 소개 GIF 만들기(명세 외 요청): reports/shots/frames/<flow>/NN.png + captions.json → reports/feature-tour/<flow>.gif

실행: (backend 가상환경의 Pillow 사용) cd backend && uv run python ../scripts/make_tour_gifs.py
"""
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "reports" / "shots" / "frames"
OUT = ROOT / "reports" / "feature-tour"
WIDTH = 1000          # 출력 폭(px)
HOLD_MS = 1700        # 프레임당 표시 시간
FONTS = [("/System/Library/Fonts/AppleSDGothicNeo.ttc", 2), ("/System/Library/Fonts/AppleSDGothicNeo.ttc", 0)]


def font(size):
    for path, idx in FONTS:
        if Path(path).is_file():
            return ImageFont.truetype(path, size, index=idx)
    return ImageFont.load_default()


def caption(img, text, step, total):
    w, h = img.size
    bar = 46
    canvas = Image.new("RGB", (w, h + bar), (18, 41, 74))
    canvas.paste(img, (0, 0))
    d = ImageDraw.Draw(canvas)
    f, fs = font(19), font(14)
    d.rounded_rectangle((14, h + 11, 62, h + 35), 12, fill=(37, 99, 235))
    d.text((38, h + 23), f"{step}/{total}", font=fs, fill="white", anchor="mm")
    d.text((76, h + 23), text, font=f, fill="white", anchor="lm")
    for i in range(total):  # 진행 점
        x = w - 18 - (total - 1 - i) * 14
        d.ellipse((x - 4, h + 19, x + 4, h + 27), fill=(255, 255, 255) if i < step else (82, 110, 150))
    return canvas


def build(flow_dir: Path) -> Path | None:
    caps = json.loads((flow_dir / "captions.json").read_text(encoding="utf-8"))
    frames = []
    for i, text in enumerate(caps):
        p = flow_dir / f"{i:02d}.png"
        if not p.is_file():
            continue
        img = Image.open(p).convert("RGB")
        img = img.resize((WIDTH, round(img.height * WIDTH / img.width)), Image.LANCZOS)
        frames.append(caption(img, text, i + 1, len(caps)))
    if not frames:
        return None
    pal = [f.quantize(colors=200, method=Image.MEDIANCUT, dither=Image.NONE) for f in frames]
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / f"{flow_dir.name}.gif"
    durations = [HOLD_MS] * (len(pal) - 1) + [HOLD_MS + 1200]
    pal[0].save(out, save_all=True, append_images=pal[1:], duration=durations, loop=0, optimize=True, disposal=1)
    return out


if __name__ == "__main__":
    names = sys.argv[1:]
    for d in sorted(SRC.iterdir()):
        if d.is_dir() and (not names or d.name in names):
            out = build(d)
            if out:
                print(f"{out.relative_to(ROOT)}  {out.stat().st_size // 1024}KB")

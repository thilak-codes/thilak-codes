#!/usr/bin/env python3
"""
build_profile.py - ONE file that builds everything for the profile README.

  contrib-heatmap.svg  <- your real contributions (refreshed daily by GitHub Actions)
  thilak-ascii.svg     <- ASCII portrait (made once; placeholder until you add a photo)
  info-card.svg        <- neofetch-style card (made once)

Run by the workflow every day. Locally:  python build_profile.py [--demo] [--all]
  --demo : fake contribution data (testing only)
  --all  : also rebuild the ASCII portrait and info card even if they exist
"""
import os
import random
import re
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from xml.sax.saxutils import escape

USER = os.environ.get("GITHUB_USER", "thilak-codes")
MONO = "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"
BG, FG, MUTED = "#0d1117", "#c9d1d9", "#8b949e"

# =========================================================== 1. HEATMAP
PALETTE = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353", "#69f0a0"]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def fetch_days(user):
    import requests
    from bs4 import BeautifulSoup

    url = f"https://github.com/users/{user}/contributions"
    headers = {"User-Agent": "Mozilla/5.0 (profile-readme-bot)"}
    html, last = None, None
    for attempt in range(1, 4):
        try:
            r = requests.get(url, headers=headers, timeout=30)
            r.raise_for_status()
            html = r.text
            break
        except Exception as exc:  # noqa: BLE001
            last = exc
            print(f"[warn] fetch attempt {attempt} failed: {exc}")
            time.sleep(3 * attempt)
    if html is None:
        raise RuntimeError(f"could not fetch {url}: {last}")

    soup = BeautifulSoup(html, "html.parser")
    tips = {t.get("for"): t.get_text(" ", strip=True) for t in soup.find_all("tool-tip") if t.get("for")}
    days = []
    for cell in soup.select("td.ContributionCalendar-day[data-date]"):
        level = int(cell.get("data-level", 0) or 0)
        text = tips.get(cell.get("id", ""), "")
        m = re.match(r"\s*([\d,]+)\s+contribution", text)
        if m:
            count = int(m.group(1).replace(",", ""))
        elif text.lower().startswith("no contribution"):
            count = 0
        else:
            count = level
        days.append({"date": cell["data-date"], "count": count, "level": level})
    days.sort(key=lambda d: d["date"])
    if not days:
        raise RuntimeError("no contribution cells found (GitHub HTML changed?)")
    return days


def demo_days():
    rnd = random.Random(7)
    start = date.today() - timedelta(days=364)
    out = []
    for i in range(365):
        d = start + timedelta(days=i)
        c = rnd.choice([0, 0, 0, 1, 2, 3, 5, 8])
        out.append({"date": d.isoformat(), "count": c,
                    "level": 0 if c == 0 else 1 if c < 3 else 2 if c < 5 else 3 if c < 8 else 4})
    return out


def stats_for(days):
    today = date.today().isoformat()
    past = [d for d in days if d["date"] <= today]
    total = sum(d["count"] for d in past)
    longest = run = 0
    for d in past:
        run = run + 1 if d["count"] > 0 else 0
        longest = max(longest, run)
    current = 0
    for d in reversed(past):
        if d["count"] > 0:
            current += 1
        elif d["date"] == today:
            continue
        else:
            break
    best = max((d["count"] for d in past), default=0)
    return total, current, longest, best


def heatmap_svg(days):
    W, LEFT, TOP, RIGHT, GAP = 860, 38, 40, 16, 3
    total, current, longest, best = stats_for(days)
    parse = lambda s: datetime.strptime(s, "%Y-%m-%d").date()
    first = parse(days[0]["date"])
    first_sunday = first - timedelta(days=(first.weekday() + 1) % 7)
    n_weeks = ((parse(days[-1]["date"]) - first_sunday).days // 7) + 1
    pitch = (W - LEFT - RIGHT) / n_weeks
    cell = pitch - GAP
    max_count = max((d["count"] for d in days), default=0)
    grid_h = 7 * pitch
    h = int(TOP + grid_h + 56)

    css = (f"text{{font-family:{MONO};font-size:11px;fill:{MUTED}}}"
           ".c{opacity:0;animation:drop .5s ease-out forwards}"
           "@keyframes drop{from{opacity:0;transform:translateY(-8px)}to{opacity:1;transform:translateY(0)}}")
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {h}" width="{W}" height="{h}" '
           f'role="img" aria-label="Contribution heatmap">',
           f"<style>{css}</style>", f'<rect width="{W}" height="{h}" rx="10" fill="{BG}"/>']
    for row, name in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        out.append(f'<text x="8" y="{TOP + row * pitch + cell * 0.8:.1f}">{name}</text>')
    last_month = None
    for d in days:
        dt = parse(d["date"])
        wk = (dt - first_sunday).days // 7
        dow = (dt.weekday() + 1) % 7
        x, y = LEFT + wk * pitch, TOP + dow * pitch
        if dow == 0 and dt.month != last_month:
            out.append(f'<text x="{x:.1f}" y="{TOP - 10}">{MONTHS[dt.month - 1]}</text>')
            last_month = dt.month
        lvl = int(d["level"])
        if lvl >= 4 and max_count >= 10 and d["count"] >= 0.85 * max_count:
            lvl = 5
        tip = f'{d["count"]} contribution{"s" if d["count"] != 1 else ""} on {d["date"]}'
        out.append(f'<rect class="c" x="{x:.1f}" y="{y:.1f}" width="{cell:.1f}" height="{cell:.1f}" rx="3" '
                   f'fill="{PALETTE[lvl]}" style="animation-delay:{(wk + dow) * 0.015:.3f}s"><title>{tip}</title></rect>')
    fy = TOP + grid_h + 26
    out.append(f'<text x="{LEFT}" y="{fy:.0f}" style="fill:{FG};font-size:12px">{total:,} contributions in the last year</text>')
    out.append(f'<text x="{LEFT}" y="{fy + 18:.0f}">current streak {current}d  ·  longest streak {longest}d  ·  best day {best}</text>')
    lx = W - RIGHT - (6 * 16 + 70)
    out.append(f'<text x="{lx}" y="{fy:.0f}">Less</text>')
    for i, c in enumerate(PALETTE):
        out.append(f'<rect x="{lx + 34 + i * 16}" y="{fy - 10:.0f}" width="12" height="12" rx="3" fill="{c}"/>')
    out.append(f'<text x="{lx + 34 + 6 * 16 + 4}" y="{fy:.0f}">More</text>')
    out.append("</svg>")
    return "\n".join(out)


# ======================================================= 2. ASCII PORTRAIT
INITIALS = "TSM"
COLS, CHAR_W, LINE_H, FONT_SIZE = 100, 4.8, 9.6, 8
RAMP = " .`:-=+*cs#%@"
ROW_DELAY, ROW_DUR = 0.07, 0.55


def portrait_image():
    from PIL import Image, ImageDraw, ImageFont

    photo = Path("source-prepped.png")
    if photo.exists():
        print("Using source-prepped.png for the portrait")
        return Image.open(photo)
    print(f"No source-prepped.png - making a placeholder from '{INITIALS}'")
    w, h = 1000, 530
    img = Image.new("L", (w, h), 255)
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.load_default(size=480)
    except TypeError:
        font = ImageFont.load_default()
    b = draw.textbbox((0, 0), INITIALS, font=font, stroke_width=14)
    draw.text(((w - (b[2] - b[0])) / 2 - b[0], (h - (b[3] - b[1])) / 2 - b[1]), INITIALS,
              font=font, fill=40, stroke_width=14, stroke_fill=40)
    return img


def ascii_svg():
    from PIL import Image

    img = portrait_image().convert("L")
    rows_n = max(1, round(COLS * (img.height / img.width) * (CHAR_W / LINE_H)))
    img = img.resize((COLS, rows_n), Image.LANCZOS)
    px = img.load()
    rows = ["".join(RAMP[int((255 - px[x, y]) / 255 * (len(RAMP) - 1) + 0.5)] for x in range(COLS))
            for y in range(rows_n)]
    w, h = COLS * CHAR_W, rows_n * LINE_H
    defs, body = [], []
    for i, row in enumerate(rows):
        s = row.rstrip()
        if not s.strip():
            continue
        lead, text = len(s) - len(s.lstrip(" ")), s.lstrip(" ")
        y, begin = i * LINE_H, i * ROW_DELAY
        defs.append(f'<clipPath id="c{i}"><rect x="0" y="{y:.1f}" width="0" height="{LINE_H:.1f}">'
                    f'<animate attributeName="width" from="0" to="{w:.1f}" dur="{ROW_DUR}s" begin="{begin:.2f}s" fill="freeze"/>'
                    f'</rect></clipPath>')
        body.append(f'<text x="{lead * CHAR_W:.1f}" y="{y + LINE_H * 0.78:.1f}" font-family="{MONO}" font-size="{FONT_SIZE}" '
                    f'fill="{FG}" xml:space="preserve" textLength="{len(text) * CHAR_W:.1f}" lengthAdjust="spacing" '
                    f'clip-path="url(#c{i})">{escape(text)}</text>')
        body.append(f'<rect x="0" y="{y:.1f}" width="{CHAR_W:.1f}" height="{LINE_H:.1f}" fill="{FG}" opacity="0">'
                    f'<set attributeName="opacity" to="1" begin="{begin:.2f}s"/>'
                    f'<animate attributeName="x" from="0" to="{w - CHAR_W:.1f}" dur="{ROW_DUR}s" begin="{begin:.2f}s" fill="freeze"/>'
                    f'<set attributeName="opacity" to="0" begin="{begin + ROW_DUR:.2f}s"/></rect>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:.1f} {h:.1f}" width="{w:.0f}" height="{h:.0f}" '
            f'role="img" aria-label="ASCII portrait"><rect width="{w:.1f}" height="{h:.1f}" rx="10" fill="{BG}"/>'
            f'<defs>{"".join(defs)}</defs>{"".join(body)}</svg>')


# ========================================================= 3. INFO CARD
USER_HOST = "thilak@github"
LINES = [
    ("Name", "Thilak S M"),
    ("Now", "B.E. CSE student (2nd year)"),
    ("College", "K.Ramakrishnan College of Engg"),
    ("Stack", "Python · SQL · C"),
    ("Built", "CLI Calculator · CLI To-Do App"),
    ("Learning", "Data Analysis · Power BI · DevOps"),
    ("Workshops", "Cybersecurity · Web · Automation"),
    ("Languages", "English · Tamil"),
    ("Seeking", "Software development internship"),
    ("Email", "thilak080207@gmail.com"),
    ("LinkedIn", "linkedin.com/in/smthilak"),
]
KEY_COLORS = ["#ff7b72", "#79c0ff", "#d2a8ff", "#7ee787", "#ffa657"]


def info_card_svg():
    W, TITLE_H, PAD, VAL_X, LH, STEP = 490, 34, 22, 128, 24, 0.14
    h = TITLE_H + 64 + len(LINES) * LH + 24
    css = (f"text{{font-family:{MONO};font-size:13px}}.k{{font-weight:700}}"
           ".l{opacity:0;animation:in .45s ease-out forwards}"
           "@keyframes in{from{opacity:0;transform:translateX(-10px)}to{opacity:1;transform:translateX(0)}}")
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {h}" width="{W}" height="{h}" role="img" aria-label="Info card">',
           f"<style>{css}</style>", f'<rect width="{W}" height="{h}" rx="10" fill="{BG}"/>',
           f'<path d="M0 10a10 10 0 0 1 10-10h{W - 20}a10 10 0 0 1 10 10v{TITLE_H - 10}H0z" fill="#161b22"/>',
           '<circle cx="20" cy="17" r="5.5" fill="#ff5f56"/><circle cx="40" cy="17" r="5.5" fill="#ffbd2e"/><circle cx="60" cy="17" r="5.5" fill="#27c93f"/>',
           f'<text x="{W / 2}" y="22" text-anchor="middle" fill="{MUTED}" font-size="12">neofetch</text>']
    y, delay = TITLE_H + 34, 0.2
    out.append(f'<text class="l k" x="{PAD}" y="{y}" fill="#79c0ff" style="animation-delay:{delay:.2f}s">{escape(USER_HOST)}</text>')
    y += 20; delay += STEP
    out.append(f'<text class="l" x="{PAD}" y="{y}" fill="{MUTED}" style="animation-delay:{delay:.2f}s">{"-" * len(USER_HOST)}</text>')
    y += 22
    for i, (k, v) in enumerate(LINES):
        delay += STEP
        out.append(f'<text class="l" x="{PAD}" y="{y}" style="animation-delay:{delay:.2f}s">'
                   f'<tspan class="k" fill="{KEY_COLORS[i % 5]}">{escape(k)}</tspan>'
                   f'<tspan x="{VAL_X}" fill="{FG}">{escape(v)}</tspan></text>')
        y += LH
    delay += STEP
    for j, c in enumerate(["#ff5f56", "#ffbd2e", "#27c93f", "#79c0ff", "#d2a8ff", "#c9d1d9"]):
        out.append(f'<rect class="l" x="{PAD + j * 22}" y="{y - 6}" width="18" height="10" rx="2" fill="{c}" style="animation-delay:{delay:.2f}s"/>')
    out.append("</svg>")
    return "\n".join(out)


# =============================================================== MAIN
def main():
    demo, force_all = "--demo" in sys.argv, "--all" in sys.argv
    ok = True

    # heatmap: refreshed every run
    try:
        days = demo_days() if demo else fetch_days(USER)
        Path("contrib-heatmap.svg").write_text(heatmap_svg(days), encoding="utf-8")
        print(f"Wrote contrib-heatmap.svg ({len(days)} days, {stats_for(days)[0]} contributions)")
    except Exception as exc:  # noqa: BLE001
        ok = False
        print(f"[error] heatmap not updated: {exc}")

    # portrait + card: only when missing (so a later real photo is never overwritten)
    for name, fn in (("thilak-ascii.svg", ascii_svg), ("info-card.svg", info_card_svg)):
        if force_all or not Path(name).exists():
            Path(name).write_text(fn(), encoding="utf-8")
            print(f"Wrote {name}")
        else:
            print(f"Kept existing {name}")
    if not ok:
        sys.exit(1)


if __name__ == "__main__":#!/usr/bin/env python3
"""
build_profile.py - ONE file that builds everything for the profile README.

  contrib-heatmap.svg  <- your real contributions (refreshed daily by GitHub Actions)
  thilak-ascii.svg     <- ASCII portrait (made once; placeholder until you add a photo)
  info-card.svg        <- neofetch-style card (made once)

Run by the workflow every day. Locally:  python build_profile.py [--demo] [--all]
  --demo : fake contribution data (testing only)
  --all  : also rebuild the ASCII portrait and info card even if they exist
"""
import os
import random
import re
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from xml.sax.saxutils import escape

USER = os.environ.get("GITHUB_USER", "thilak-codes")
MONO = "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"
BG, FG, MUTED = "#0d1117", "#c9d1d9", "#8b949e"

# =========================================================== 1. HEATMAP
PALETTE = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353", "#69f0a0"]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def fetch_days(user):
    import requests
    from bs4 import BeautifulSoup

    url = f"https://github.com/users/{user}/contributions"
    headers = {"User-Agent": "Mozilla/5.0 (profile-readme-bot)"}
    html, last = None, None
    for attempt in range(1, 4):
        try:
            r = requests.get(url, headers=headers, timeout=30)
            r.raise_for_status()
            html = r.text
            break
        except Exception as exc:  # noqa: BLE001
            last = exc
            print(f"[warn] fetch attempt {attempt} failed: {exc}")
            time.sleep(3 * attempt)
    if html is None:
        raise RuntimeError(f"could not fetch {url}: {last}")

    soup = BeautifulSoup(html, "html.parser")
    tips = {t.get("for"): t.get_text(" ", strip=True) for t in soup.find_all("tool-tip") if t.get("for")}
    days = []
    for cell in soup.select("td.ContributionCalendar-day[data-date]"):
        level = int(cell.get("data-level", 0) or 0)
        text = tips.get(cell.get("id", ""), "")
        m = re.match(r"\s*([\d,]+)\s+contribution", text)
        if m:
            count = int(m.group(1).replace(",", ""))
        elif text.lower().startswith("no contribution"):
            count = 0
        else:
            count = level
        days.append({"date": cell["data-date"], "count": count, "level": level})
    days.sort(key=lambda d: d["date"])
    if not days:
        raise RuntimeError("no contribution cells found (GitHub HTML changed?)")
    return days


def demo_days():
    rnd = random.Random(7)
    start = date.today() - timedelta(days=364)
    out = []
    for i in range(365):
        d = start + timedelta(days=i)
        c = rnd.choice([0, 0, 0, 1, 2, 3, 5, 8])
        out.append({"date": d.isoformat(), "count": c,
                    "level": 0 if c == 0 else 1 if c < 3 else 2 if c < 5 else 3 if c < 8 else 4})
    return out


def stats_for(days):
    today = date.today().isoformat()
    past = [d for d in days if d["date"] <= today]
    total = sum(d["count"] for d in past)
    longest = run = 0
    for d in past:
        run = run + 1 if d["count"] > 0 else 0
        longest = max(longest, run)
    current = 0
    for d in reversed(past):
        if d["count"] > 0:
            current += 1
        elif d["date"] == today:
            continue
        else:
            break
    best = max((d["count"] for d in past), default=0)
    return total, current, longest, best


def heatmap_svg(days):
    W, LEFT, TOP, RIGHT, GAP = 860, 38, 40, 16, 3
    total, current, longest, best = stats_for(days)
    parse = lambda s: datetime.strptime(s, "%Y-%m-%d").date()
    first = parse(days[0]["date"])
    first_sunday = first - timedelta(days=(first.weekday() + 1) % 7)
    n_weeks = ((parse(days[-1]["date"]) - first_sunday).days // 7) + 1
    pitch = (W - LEFT - RIGHT) / n_weeks
    cell = pitch - GAP
    max_count = max((d["count"] for d in days), default=0)
    grid_h = 7 * pitch
    h = int(TOP + grid_h + 56)

    css = (f"text{{font-family:{MONO};font-size:11px;fill:{MUTED}}}"
           ".c{opacity:0;animation:drop .5s ease-out forwards}"
           "@keyframes drop{from{opacity:0;transform:translateY(-8px)}to{opacity:1;transform:translateY(0)}}")
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {h}" width="{W}" height="{h}" '
           f'role="img" aria-label="Contribution heatmap">',
           f"<style>{css}</style>", f'<rect width="{W}" height="{h}" rx="10" fill="{BG}"/>']
    for row, name in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        out.append(f'<text x="8" y="{TOP + row * pitch + cell * 0.8:.1f}">{name}</text>')
    last_month = None
    for d in days:
        dt = parse(d["date"])
        wk = (dt - first_sunday).days // 7
        dow = (dt.weekday() + 1) % 7
        x, y = LEFT + wk * pitch, TOP + dow * pitch
        if dow == 0 and dt.month != last_month:
            out.append(f'<text x="{x:.1f}" y="{TOP - 10}">{MONTHS[dt.month - 1]}</text>')
            last_month = dt.month
        lvl = int(d["level"])
        if lvl >= 4 and max_count >= 10 and d["count"] >= 0.85 * max_count:
            lvl = 5
        tip = f'{d["count"]} contribution{"s" if d["count"] != 1 else ""} on {d["date"]}'
        out.append(f'<rect class="c" x="{x:.1f}" y="{y:.1f}" width="{cell:.1f}" height="{cell:.1f}" rx="3" '
                   f'fill="{PALETTE[lvl]}" style="animation-delay:{(wk + dow) * 0.015:.3f}s"><title>{tip}</title></rect>')
    fy = TOP + grid_h + 26
    out.append(f'<text x="{LEFT}" y="{fy:.0f}" style="fill:{FG};font-size:12px">{total:,} contributions in the last year</text>')
    out.append(f'<text x="{LEFT}" y="{fy + 18:.0f}">current streak {current}d  ·  longest streak {longest}d  ·  best day {best}</text>')
    lx = W - RIGHT - (6 * 16 + 70)
    out.append(f'<text x="{lx}" y="{fy:.0f}">Less</text>')
    for i, c in enumerate(PALETTE):
        out.append(f'<rect x="{lx + 34 + i * 16}" y="{fy - 10:.0f}" width="12" height="12" rx="3" fill="{c}"/>')
    out.append(f'<text x="{lx + 34 + 6 * 16 + 4}" y="{fy:.0f}">More</text>')
    out.append("</svg>")
    return "\n".join(out)


# ======================================================= 2. ASCII PORTRAIT
INITIALS = "TSM"
COLS, CHAR_W, LINE_H, FONT_SIZE = 100, 4.8, 9.6, 8
RAMP = " .`:-=+*cs#%@"
ROW_DELAY, ROW_DUR = 0.07, 0.55


def portrait_image():
    from PIL import Image, ImageDraw, ImageFont

    photo = Path("source-prepped.png")
    if photo.exists():
        print("Using source-prepped.png for the portrait")
        return Image.open(photo)
    print(f"No source-prepped.png - making a placeholder from '{INITIALS}'")
    w, h = 1000, 530
    img = Image.new("L", (w, h), 255)
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.load_default(size=480)
    except TypeError:
        font = ImageFont.load_default()
    b = draw.textbbox((0, 0), INITIALS, font=font, stroke_width=14)
    draw.text(((w - (b[2] - b[0])) / 2 - b[0], (h - (b[3] - b[1])) / 2 - b[1]), INITIALS,
              font=font, fill=40, stroke_width=14, stroke_fill=40)
    return img


def ascii_svg():
    from PIL import Image

    img = portrait_image().convert("L")
    rows_n = max(1, round(COLS * (img.height / img.width) * (CHAR_W / LINE_H)))
    img = img.resize((COLS, rows_n), Image.LANCZOS)
    px = img.load()
    rows = ["".join(RAMP[int((255 - px[x, y]) / 255 * (len(RAMP) - 1) + 0.5)] for x in range(COLS))
            for y in range(rows_n)]
    w, h = COLS * CHAR_W, rows_n * LINE_H
    defs, body = [], []
    for i, row in enumerate(rows):
        s = row.rstrip()
        if not s.strip():
            continue
        lead, text = len(s) - len(s.lstrip(" ")), s.lstrip(" ")
        y, begin = i * LINE_H, i * ROW_DELAY
        defs.append(f'<clipPath id="c{i}"><rect x="0" y="{y:.1f}" width="0" height="{LINE_H:.1f}">'
                    f'<animate attributeName="width" from="0" to="{w:.1f}" dur="{ROW_DUR}s" begin="{begin:.2f}s" fill="freeze"/>'
                    f'</rect></clipPath>')
        body.append(f'<text x="{lead * CHAR_W:.1f}" y="{y + LINE_H * 0.78:.1f}" font-family="{MONO}" font-size="{FONT_SIZE}" '
                    f'fill="{FG}" xml:space="preserve" textLength="{len(text) * CHAR_W:.1f}" lengthAdjust="spacing" '
                    f'clip-path="url(#c{i})">{escape(text)}</text>')
        body.append(f'<rect x="0" y="{y:.1f}" width="{CHAR_W:.1f}" height="{LINE_H:.1f}" fill="{FG}" opacity="0">'
                    f'<set attributeName="opacity" to="1" begin="{begin:.2f}s"/>'
                    f'<animate attributeName="x" from="0" to="{w - CHAR_W:.1f}" dur="{ROW_DUR}s" begin="{begin:.2f}s" fill="freeze"/>'
                    f'<set attributeName="opacity" to="0" begin="{begin + ROW_DUR:.2f}s"/></rect>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:.1f} {h:.1f}" width="{w:.0f}" height="{h:.0f}" '
            f'role="img" aria-label="ASCII portrait"><rect width="{w:.1f}" height="{h:.1f}" rx="10" fill="{BG}"/>'
            f'<defs>{"".join(defs)}</defs>{"".join(body)}</svg>')


# ========================================================= 3. INFO CARD
USER_HOST = "thilak@github"
LINES = [
    ("Name", "Thilak S M"),
    ("Now", "B.E. CSE student (2nd year)"),
    ("College", "K.Ramakrishnan College of Engg"),
    ("Stack", "Python · SQL · C"),
    ("Built", "CLI Calculator · CLI To-Do App"),
    ("Learning", "Data Analysis · Power BI · DevOps"),
    ("Workshops", "Cybersecurity · Web · Automation"),
    ("Languages", "English · Tamil"),
    ("Seeking", "Software development internship"),
    ("Email", "thilak080207@gmail.com"),
    ("LinkedIn", "linkedin.com/in/smthilak"),
]
KEY_COLORS = ["#ff7b72", "#79c0ff", "#d2a8ff", "#7ee787", "#ffa657"]


def info_card_svg():
    W, TITLE_H, PAD, VAL_X, LH, STEP = 490, 34, 22, 128, 24, 0.14
    h = TITLE_H + 64 + len(LINES) * LH + 24
    css = (f"text{{font-family:{MONO};font-size:13px}}.k{{font-weight:700}}"
           ".l{opacity:0;animation:in .45s ease-out forwards}"
           "@keyframes in{from{opacity:0;transform:translateX(-10px)}to{opacity:1;transform:translateX(0)}}")
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {h}" width="{W}" height="{h}" role="img" aria-label="Info card">',
           f"<style>{css}</style>", f'<rect width="{W}" height="{h}" rx="10" fill="{BG}"/>',
           f'<path d="M0 10a10 10 0 0 1 10-10h{W - 20}a10 10 0 0 1 10 10v{TITLE_H - 10}H0z" fill="#161b22"/>',
           '<circle cx="20" cy="17" r="5.5" fill="#ff5f56"/><circle cx="40" cy="17" r="5.5" fill="#ffbd2e"/><circle cx="60" cy="17" r="5.5" fill="#27c93f"/>',
           f'<text x="{W / 2}" y="22" text-anchor="middle" fill="{MUTED}" font-size="12">neofetch</text>']
    y, delay = TITLE_H + 34, 0.2
    out.append(f'<text class="l k" x="{PAD}" y="{y}" fill="#79c0ff" style="animation-delay:{delay:.2f}s">{escape(USER_HOST)}</text>')
    y += 20; delay += STEP
    out.append(f'<text class="l" x="{PAD}" y="{y}" fill="{MUTED}" style="animation-delay:{delay:.2f}s">{"-" * len(USER_HOST)}</text>')
    y += 22
    for i, (k, v) in enumerate(LINES):
        delay += STEP
        out.append(f'<text class="l" x="{PAD}" y="{y}" style="animation-delay:{delay:.2f}s">'
                   f'<tspan class="k" fill="{KEY_COLORS[i % 5]}">{escape(k)}</tspan>'
                   f'<tspan x="{VAL_X}" fill="{FG}">{escape(v)}</tspan></text>')
        y += LH
    delay += STEP
    for j, c in enumerate(["#ff5f56", "#ffbd2e", "#27c93f", "#79c0ff", "#d2a8ff", "#c9d1d9"]):
        out.append(f'<rect class="l" x="{PAD + j * 22}" y="{y - 6}" width="18" height="10" rx="2" fill="{c}" style="animation-delay:{delay:.2f}s"/>')
    out.append("</svg>")
    return "\n".join(out)


# =============================================================== MAIN
def main():
    demo, force_all = "--demo" in sys.argv, "--all" in sys.argv
    ok = True

    # heatmap: refreshed every run
    try:
        days = demo_days() if demo else fetch_days(USER)
        Path("contrib-heatmap.svg").write_text(heatmap_svg(days), encoding="utf-8")
        print(f"Wrote contrib-heatmap.svg ({len(days)} days, {stats_for(days)[0]} contributions)")
    except Exception as exc:  # noqa: BLE001
        ok = False
        print(f"[error] heatmap not updated: {exc}")

    # portrait + card: only when missing (so a later real photo is never overwritten)
    for name, fn in (("thilak-ascii.svg", ascii_svg), ("info-card.svg", info_card_svg)):
        if force_all or not Path(name).exists():
            Path(name).write_text(fn(), encoding="utf-8")
            print(f"Wrote {name}")
        else:
            print(f"Kept existing {name}")
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()

    main()

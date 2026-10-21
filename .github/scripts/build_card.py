#!/usr/bin/env python3
"""Wrap the Platane/snk snake animation in a stats card.

Reads  : raw snake SVG written by Platane/snk (--snake)
Fetches: the contribution calendar through the GitHub GraphQL API (GITHUB_TOKEN)
Writes : one self-contained card SVG (--out)

Standard library only, so the workflow needs no pip install.
"""
import argparse
import datetime as dt
import json
import os
import re
import urllib.request

# ---- palette (matches assets/hero.svg and assets/stack.svg) -----------------
BG, GRID_MINOR, GRID_MAJOR, FRAME = "#0E2238", "#16324F", "#1F446B", "#8FB4D9"
INK, SOFT, DIM, AMBER = "#F4F8FC", "#9CC1E6", "#6F96BE", "#F2B544"
RAMP = ["#1B3B5E", "#245C94", "#3585CF", "#6DB6F2", "#D6E8FA"]  # empty -> busiest

W = 1200
PAD = 56
GRID_W = W - 2 * PAD


def fetch_calendar(login, token):
    query = (
        "query($login:String!){user(login:$login){contributionsCollection{"
        "contributionCalendar{weeks{contributionDays{contributionCount date}}}}}}"
    )
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": {"login": login}}).encode(),
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "profile-snake-card",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def parse_calendar(payload):
    if payload.get("errors"):
        raise RuntimeError(payload["errors"][0].get("message", "GraphQL error"))
    weeks = payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    days = [(d["date"], d["contributionCount"]) for w in weeks for d in w["contributionDays"]]
    return sorted(days)


def compute_stats(days):
    counts = [c for _, c in days]
    total = sum(counts)
    # a streak is still alive if today has no commits yet, so skip an empty last day
    end = len(counts) - 1
    if end >= 0 and counts[end] == 0:
        end -= 1
    current = 0
    while end >= 0 and counts[end] > 0:
        current += 1
        end -= 1
    longest = run = 0
    for c in counts:
        run = run + 1 if c > 0 else 0
        longest = max(longest, run)
    return {
        "total": total,
        "current": current,
        "longest": longest,
        "pace": total / len(counts) if counts else 0.0,
        "best": max(counts) if counts else 0,
    }


def stat_value(text, unit=""):
    dx = 2 if unit in ("d", "/day") else 8
    tail = f'<tspan font-size="16" font-weight="400" fill="{DIM}" dx="{dx}">{unit}</tspan>' if unit else ""
    return f"{text}{tail}"


def build(snake_raw, stats, updated):
    m = re.match(
        r'\s*<svg viewBox="(-?[\d.]+) (-?[\d.]+) ([\d.]+) ([\d.]+)"[^>]*>(.*)</svg>\s*$',
        snake_raw,
        re.S,
    )
    if not m:
        raise RuntimeError("unexpected snk output: could not read the root <svg>")
    vx, vy, vw, vh = (float(m.group(i)) for i in range(1, 5))
    inner = re.sub(r"<desc>.*?</desc>", "", m.group(5), flags=re.S)

    # crop the empty band above the grid so the card stays compact
    crop = 20
    nest_vb = f"{vx:g} {vy + crop:g} {vw:g} {vh - crop - 4:g}"
    scale = GRID_W / (vw - 32)  # snk pads 16 units each side of the grid
    grid_h = (vh - crop - 4) * scale
    nest_x = PAD + vx * scale   # vx is -16, so the viewport starts a little left of PAD
    nest_w = vw * scale

    grid_y = 124
    rule_y = round(grid_y + grid_h + 26)
    label_y, value_y = rule_y + 28, rule_y + 66
    foot_y = value_y + 38
    H = foot_y + 28

    cols = [
        (f"{stats['total']:,}", "", "contributions, last year", INK),
        (str(stats["current"]), "d", "current streak", AMBER),
        (str(stats["longest"]), "d", "longest streak", INK),
        (f"{stats['pace']:.1f}", "/day", "average per day", INK),
        (str(stats["best"]), "", "best day", SOFT),
    ]
    cw = GRID_W / len(cols)
    col_svg = []
    for i, (val, unit, label, color) in enumerate(cols):
        x = PAD + i * cw + (14 if i else 0)
        if i:
            col_svg.append(
                f'<line x1="{PAD + i * cw:.1f}" y1="{rule_y + 14}" x2="{PAD + i * cw:.1f}" '
                f'y2="{value_y + 12}" stroke="{FRAME}" stroke-opacity=".45"/>'
            )
        col_svg.append(f'<text class="fc-mono" x="{x:.1f}" y="{label_y}" font-size="12" fill="{DIM}">{label}</text>')
        col_svg.append(
            f'<text class="fc-sans" x="{x:.1f}" y="{value_y}" font-size="36" font-weight="700" '
            f'fill="{color}">{stat_value(val, unit)}</text>'
        )

    legend = [f'<text class="fc-mono" x="{W - PAD - 144}" y="96" font-size="11" fill="{DIM}">less</text>']
    for i, c in enumerate(RAMP):
        legend.append(f'<rect x="{W - PAD - 108 + i * 14}" y="87" width="10" height="10" rx="2" fill="{c}"/>')
    legend.append(f'<text class="fc-mono" x="{W - PAD - 32}" y="96" font-size="11" fill="{DIM}">more</text>')

    summary = (
        f"Contribution snake card. {stats['total']:,} contributions in the last year, "
        f"current streak {stats['current']} days, longest streak {stats['longest']} days, "
        f"{stats['pace']:.1f} per day on average, best day {stats['best']}."
    )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-labelledby="fc-t fc-d">
  <title id="fc-t">contribution snake</title>
  <desc id="fc-d">{summary}</desc>
  <defs>
    <pattern id="fc-minor" width="20" height="20" patternUnits="userSpaceOnUse"><path d="M20 0H0V20" fill="none" stroke="{GRID_MINOR}" stroke-width="1"/></pattern>
    <pattern id="fc-major" width="100" height="100" patternUnits="userSpaceOnUse"><rect width="100" height="100" fill="url(#fc-minor)"/><path d="M100 0H0V100" fill="none" stroke="{GRID_MAJOR}" stroke-width="1"/></pattern>
    <style>
      .fc-sans{{font-family:"Helvetica Neue",Helvetica,Arial,"Segoe UI",sans-serif}}
      .fc-mono{{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,"Liberation Mono",monospace}}
    </style>
  </defs>

  <rect width="{W}" height="{H}" fill="{BG}"/>
  <rect width="{W}" height="{H}" fill="url(#fc-major)"/>
  <rect x="16" y="16" width="{W - 32}" height="{H - 32}" fill="none" stroke="{FRAME}" stroke-width="1.5"/>

  <text class="fc-sans" x="{PAD}" y="76" font-size="28" font-weight="700" fill="{INK}">contribution snake</text>
  <text class="fc-mono" x="{PAD}" y="98" font-size="13" fill="{DIM}">eating squares, rebuilt daily at 06:23 utc</text>
  <circle cx="{W - PAD - 4}" cy="66" r="4" fill="{AMBER}"/>
  <text class="fc-mono" x="{W - PAD - 18}" y="70" font-size="12" text-anchor="end" fill="{DIM}">updated {updated}</text>
  {chr(10).join("  " + l for l in legend).strip()}

  <svg x="{nest_x:.1f}" y="{grid_y}" width="{nest_w:.1f}" height="{grid_h:.1f}" viewBox="{nest_vb}">{inner}</svg>

  <line x1="{PAD}" y1="{rule_y}" x2="{W - PAD}" y2="{rule_y}" stroke="{FRAME}" stroke-opacity=".6"/>
  {chr(10).join("  " + c for c in col_svg).strip()}

  <text class="fc-mono" x="{PAD}" y="{foot_y}" font-size="11" fill="{DIM}">snake path by Platane/snk, MIT</text>
</svg>
'''


MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def build_activity(days, updated):
    """Second card: contributions by month, by weekday, and four summary numbers."""
    by_month = {}
    by_weekday = [0] * 7
    for d, c in days:
        by_month[d[:7]] = by_month.get(d[:7], 0) + c
        by_weekday[dt.date.fromisoformat(d).weekday()] += c
    keys = sorted(by_month)[-12:]
    months = [(k, by_month[k]) for k in keys]
    mmax = max((v for _, v in months), default=0) or 1
    wmax = max(by_weekday) or 1

    # summary numbers
    active = sum(1 for _, c in days if c > 0)
    gap = run = 0
    for _, c in days:
        run = run + 1 if c == 0 else 0
        gap = max(gap, run)
    top_k, top_v = max(months, key=lambda kv: kv[1])
    top_wd = max(range(7), key=lambda i: by_weekday[i])
    span = f"{MONTHS[int(keys[0][5:])-1]} {keys[0][:4]} to {MONTHS[int(keys[-1][5:])-1]} {keys[-1][:4]}"

    chart_top, base = 130, 300
    ch = base - chart_top
    left_w = 664
    slot = left_w / len(months)
    bw = 34
    bars = []
    for i, (k, v) in enumerate(months):
        x = PAD + i * slot + (slot - bw) / 2
        h = max(2, round(v / mmax * ch)) if v else 2
        now = i == len(months) - 1
        fill = AMBER if now else (RAMP[4] if v == mmax else RAMP[2])
        bars.append(f'<rect x="{x:.1f}" y="{base - h}" width="{bw}" height="{h}" rx="2" fill="{fill}"/>')
        bars.append(
            f'<text class="fc-mono" x="{x + bw / 2:.1f}" y="{base - h - 8}" font-size="11" '
            f'text-anchor="middle" fill="{SOFT}">{v}</text>'
        )
        bars.append(
            f'<text class="fc-mono" x="{x + bw / 2:.1f}" y="{base + 22}" font-size="12" '
            f'text-anchor="middle" fill="{DIM}">{MONTHS[int(k[5:]) - 1]}</text>'
        )
    guides = "".join(
        f'<line x1="{PAD}" y1="{base - round(ch * f)}" x2="{PAD + left_w}" y2="{base - round(ch * f)}" '
        f'stroke="{FRAME}" stroke-opacity=".18" stroke-dasharray="2 6"/>'
        for f in (0.5, 1.0)
    )

    rx, bar_x, bar_w = 790, 842, 232
    rows = []
    for i, n in enumerate(by_weekday):
        y = chart_top + 8 + i * 28
        w = max(2, round(n / wmax * bar_w)) if n else 2
        fill = RAMP[4] if n == wmax else RAMP[2]
        rows.append(f'<text class="fc-mono" x="{rx}" y="{y + 12}" font-size="12" fill="{DIM}">{WEEKDAYS[i]}</text>')
        rows.append(f'<rect x="{bar_x}" y="{y}" width="{bar_w}" height="16" rx="2" fill="{RAMP[0]}"/>')
        rows.append(f'<rect x="{bar_x}" y="{y}" width="{w}" height="16" rx="2" fill="{fill}"/>')
        rows.append(f'<text class="fc-mono" x="{PAD + GRID_W}" y="{y + 12}" font-size="11" text-anchor="end" fill="{SOFT}">{n}</text>')

    rule_y = base + 50
    label_y, value_y = rule_y + 28, rule_y + 66
    H = value_y + 44
    cols = [
        (str(active), f"of {len(days)}", "active days", INK),
        (MONTHS[int(top_k[5:]) - 1].capitalize(), str(top_v), "busiest month", INK),
        (WEEKDAYS[top_wd].capitalize(), str(by_weekday[top_wd]), "busiest weekday", INK),
        (str(gap), "d", "longest break", SOFT),
    ]
    cw = GRID_W / len(cols)
    col_svg = []
    for i, (val, unit, label, color) in enumerate(cols):
        x = PAD + i * cw + (14 if i else 0)
        if i:
            col_svg.append(
                f'<line x1="{PAD + i * cw:.1f}" y1="{rule_y + 14}" x2="{PAD + i * cw:.1f}" '
                f'y2="{value_y + 12}" stroke="{FRAME}" stroke-opacity=".45"/>'
            )
        col_svg.append(f'<text class="fc-mono" x="{x:.1f}" y="{label_y}" font-size="12" fill="{DIM}">{label}</text>')
        col_svg.append(
            f'<text class="fc-sans" x="{x:.1f}" y="{value_y}" font-size="36" font-weight="700" '
            f'fill="{color}">{stat_value(val, unit)}</text>'
        )

    summary = (
        f"Activity card, {span}. Contributions per month: "
        + ", ".join(f"{MONTHS[int(k[5:]) - 1]} {v}" for k, v in months)
        + ". Per weekday: "
        + ", ".join(f"{WEEKDAYS[i]} {n}" for i, n in enumerate(by_weekday))
        + f". Active on {active} of {len(days)} days, longest break {gap} days."
    )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-labelledby="fa-t fa-d">
  <title id="fa-t">activity</title>
  <desc id="fa-d">{summary}</desc>
  <defs>
    <pattern id="fa-minor" width="20" height="20" patternUnits="userSpaceOnUse"><path d="M20 0H0V20" fill="none" stroke="{GRID_MINOR}" stroke-width="1"/></pattern>
    <pattern id="fa-major" width="100" height="100" patternUnits="userSpaceOnUse"><rect width="100" height="100" fill="url(#fa-minor)"/><path d="M100 0H0V100" fill="none" stroke="{GRID_MAJOR}" stroke-width="1"/></pattern>
    <style>
      .fc-sans{{font-family:"Helvetica Neue",Helvetica,Arial,"Segoe UI",sans-serif}}
      .fc-mono{{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,"Liberation Mono",monospace}}
    </style>
  </defs>

  <rect width="{W}" height="{H}" fill="{BG}"/>
  <rect width="{W}" height="{H}" fill="url(#fa-major)"/>
  <rect x="16" y="16" width="{W - 32}" height="{H - 32}" fill="none" stroke="{FRAME}" stroke-width="1.5"/>

  <text class="fc-sans" x="{PAD}" y="76" font-size="28" font-weight="700" fill="{INK}">activity by month</text>
  <text class="fc-mono" x="{PAD}" y="98" font-size="13" fill="{DIM}">{span}, current month in amber</text>
  <text class="fc-sans" x="{rx}" y="76" font-size="28" font-weight="700" fill="{INK}">by weekday</text>
  <text class="fc-mono" x="{rx}" y="98" font-size="13" fill="{DIM}">contributions per day of week</text>
  <line x1="758" y1="56" x2="758" y2="{base + 28}" stroke="{FRAME}" stroke-opacity=".45"/>

  {guides}
  {chr(10).join("  " + b for b in bars).strip()}
  {chr(10).join("  " + r for r in rows).strip()}

  <line x1="{PAD}" y1="{rule_y}" x2="{W - PAD}" y2="{rule_y}" stroke="{FRAME}" stroke-opacity=".6"/>
  {chr(10).join("  " + c for c in col_svg).strip()}
</svg>
'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snake", required=True, help="raw SVG produced by Platane/snk")
    ap.add_argument("--out", required=True)
    ap.add_argument("--activity-out", help="also write the activity card (months and weekdays)")
    ap.add_argument("--user", default=os.environ.get("GITHUB_REPOSITORY_OWNER", ""))
    ap.add_argument("--calendar-json", help="read a saved GraphQL response instead of calling the API")
    a = ap.parse_args()

    if a.calendar_json:
        payload = json.load(open(a.calendar_json))
    else:
        payload = fetch_calendar(a.user, os.environ["GITHUB_TOKEN"])
    days = parse_calendar(payload)
    stats = compute_stats(days)
    updated = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")

    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.snake) as f:
        svg = build(f.read(), stats, updated)
    with open(a.out, "w") as f:
        f.write(svg)
    print(f"wrote {a.out}: {stats}")
    if a.activity_out:
        os.makedirs(os.path.dirname(a.activity_out) or ".", exist_ok=True)
        with open(a.activity_out, "w") as f:
            f.write(build_activity(days, updated))
        print(f"wrote {a.activity_out}")


if __name__ == "__main__":
    main()

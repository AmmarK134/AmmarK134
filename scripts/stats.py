"""Renders assets/stats-dark.svg and assets/stats-light.svg for the profile README.

Runs in GitHub Actions with the built-in GITHUB_TOKEN. No third-party services.
Usage: python scripts/stats.py            (needs GITHUB_TOKEN + USERNAME env vars)
       python scripts/stats.py --mock     (renders with fake data, for local checks)
"""
import datetime as dt
import json
import os
import pathlib
import sys
import urllib.request

USERNAME = os.environ.get("USERNAME", "AmmarK134")
OUT = pathlib.Path(__file__).resolve().parent.parent / "assets"
MONO = "ui-monospace, 'SF Mono', Menlo, Consolas, 'DejaVu Sans Mono', 'Liberation Mono', monospace"

THEMES = {
    "dark": dict(primary="#e6edf3", secondary="#8b949e", accent="#d29922", frame="#484f58",
                 empty="#21262d", track="#30363d"),
    "light": dict(primary="#1f2328", secondary="#656d76", accent="#9a6700", frame="#8c959f",
                  empty="#eaeef2", track="#d8dee4"),
}

QUERY = """
query($login: String!) {
  user(login: $login) {
    followers { totalCount }
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { contributionCount date } }
      }
    }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC,
                 orderBy: {field: PUSHED_AT, direction: DESC}) {
      totalCount
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""


def fetch():
    token = os.environ["GITHUB_TOKEN"]
    body = json.dumps({"query": QUERY, "variables": {"login": USERNAME}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql", data=body,
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "site-log-stats"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.load(r)
    if "errors" in data:
        raise SystemExit("GraphQL errors: " + json.dumps(data["errors"], indent=2))
    return data["data"]["user"]


def mock():
    import random
    random.seed(7)
    today = dt.date.today()
    start = today - dt.timedelta(days=today.weekday() + 1 + 51 * 7)  # a Sunday, 52 weeks back
    weeks, d = [], start
    while d <= today:
        days = []
        for _ in range(7):
            if d > today:
                break
            days.append({"contributionCount": random.choice([0, 0, 0, 1, 2, 3, 5, 8]), "date": d.isoformat()})
            d += dt.timedelta(days=1)
        weeks.append({"contributionDays": days})
    langs = [("TypeScript", "#3178c6", 500), ("Python", "#3572A5", 320), ("JavaScript", "#f1e05a", 210),
             ("CSS", "#663399", 120), ("Java", "#b07219", 90), ("Swift", "#F05138", 60), ("HTML", "#e34c26", 40)]
    return {
        "followers": {"totalCount": 17},
        "contributionsCollection": {"contributionCalendar": {
            "totalContributions": sum(x["contributionCount"] for w in weeks for x in w["contributionDays"]),
            "weeks": weeks}},
        "repositories": {"totalCount": 27, "nodes": [
            {"stargazerCount": 1, "languages": {"edges": [
                {"size": s * 1000, "node": {"name": n, "color": c}} for n, c, s in langs]}}]},
    }


def compute(user):
    cal = user["contributionsCollection"]["contributionCalendar"]
    days = [d for w in cal["weeks"] for d in w["contributionDays"]]
    days.sort(key=lambda d: d["date"])
    # current streak: consecutive days with activity, allowing today to still be empty
    streak = 0
    for i, d in enumerate(reversed(days)):
        if d["contributionCount"] > 0:
            streak += 1
        elif i == 0:
            continue
        else:
            break
    longest = cur = 0
    for d in days:
        cur = cur + 1 if d["contributionCount"] > 0 else 0
        longest = max(longest, cur)
    repos = user["repositories"]
    stars = sum(n["stargazerCount"] for n in repos["nodes"])
    bytes_by_lang, colors = {}, {}
    for n in repos["nodes"]:
        for e in n["languages"]["edges"]:
            name = e["node"]["name"]
            bytes_by_lang[name] = bytes_by_lang.get(name, 0) + e["size"]
            colors[name] = e["node"]["color"] or "#8b949e"
    total = sum(bytes_by_lang.values()) or 1
    ranked = sorted(bytes_by_lang.items(), key=lambda kv: -kv[1])
    top = [(n, b / total, colors[n]) for n, b in ranked[:6]]
    rest = 1 - sum(p for _, p, _ in top)
    if rest > 0.005:
        top.append(("Other", rest, "#8b949e"))
    return dict(
        contributions=cal["totalContributions"], repos=repos["totalCount"], stars=stars,
        followers=user["followers"]["totalCount"], streak=streak, longest=longest,
        weeks=cal["weeks"], langs=top,
    )


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render(theme, s):
    c = THEMES[theme]
    W, H = 1200, 240
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
           f'aria-label="Field stats. {s["contributions"]} contributions in the last year, {s["repos"]} public repos, '
           f'{s["stars"]} stars, {s["streak"]} day streak.">',
           f'<style>text{{font-family:{MONO}}} .cell{{transition:none}}</style>']
    # corner marks
    corners = ""
    for (x, y, sx, sy) in [(24, 24, 1, 1), (W - 24, 24, -1, 1), (24, H - 24, 1, -1), (W - 24, H - 24, -1, -1)]:
        corners += f'<path d="M{x},{y + 22 * sy} L{x},{y} L{x + 22 * sx},{y}"/>'
    out.append(f'<g fill="none" stroke="{c["frame"]}" stroke-width="1.5">{corners}</g>')
    out.append(f'<text x="40" y="58" font-size="12" fill="{c["secondary"]}" letter-spacing="3">FIELD STATS // UPDATED {stamp}</text>')

    # headline numbers
    stats = [(s["contributions"], "CONTRIBUTIONS / 12 MO"), (s["repos"], "PUBLIC REPOS"),
             (s["stars"], "STARS"), (s["streak"], "DAY STREAK")]
    for x, (val, label) in zip((40, 250, 390, 490), stats):
        out.append(f'<text x="{x}" y="118" font-size="44" font-weight="700" fill="{c["primary"]}" letter-spacing="-1">{val}</text>')
        out.append(f'<text x="{x}" y="140" font-size="10" fill="{c["secondary"]}" letter-spacing="2">{label}</text>')
    out.append(f'<text x="40" y="168" font-size="10" fill="{c["secondary"]}" letter-spacing="2">LONGEST STREAK {s["longest"]}D · FOLLOWERS {s["followers"]}</text>')

    # language bar
    bx, by, bw, bh = 40, 186, 540, 8
    out.append(f'<rect x="{bx}" y="{by}" width="{bw}" height="{bh}" rx="4" fill="{c["track"]}"/>')
    cx = bx
    for i, (name, pct, color) in enumerate(s["langs"]):
        w = max(2, bw * pct)
        out.append(f'<rect x="{cx:.1f}" y="{by}" width="{w:.1f}" height="{bh}" fill="{color}" opacity="0.95"/>')
        cx += w
    lx = bx
    for name, pct, color in s["langs"]:
        label = f"{esc(name)} {pct * 100:.0f}%"
        out.append(f'<circle cx="{lx + 4}" cy="{by + 26}" r="4" fill="{color}"/>')
        out.append(f'<text x="{lx + 13}" y="{by + 30}" font-size="11" fill="{c["secondary"]}">{label}</text>')
        lx += 13 + len(label) * 6.8 + 14

    # contribution heatmap, last 52 weeks
    weeks = s["weeks"][-52:]
    peak = max((d["contributionCount"] for w in weeks for d in w["contributionDays"]), default=1) or 1
    hx, hy, cell, gap = 594, 64, 9, 2
    out.append(f'<text x="{hx}" y="{hy - 8}" font-size="10" fill="{c["secondary"]}" letter-spacing="2">LAST 52 WEEKS</text>')
    month_marks, last_month, last_wi = [], None, -9
    for wi, w in enumerate(weeks):
        first = dt.date.fromisoformat(w["contributionDays"][0]["date"])
        if first.month != last_month and wi - last_wi >= 3:
            last_month, last_wi = first.month, wi
            month_marks.append((hx + wi * (cell + gap), first.strftime("%b").upper()))
        for d in w["contributionDays"]:
            date = dt.date.fromisoformat(d["date"])
            di = (date.weekday() + 1) % 7  # Sunday = 0
            n = d["contributionCount"]
            if n == 0:
                fill, op = c["empty"], "1"
            else:
                fill, op = c["accent"], f"{0.3 + 0.7 * min(1.0, (n / peak) ** 0.6):.2f}"
            out.append(f'<rect class="cell" x="{hx + wi * (cell + gap)}" y="{hy + di * (cell + gap)}" width="{cell}" height="{cell}" rx="2" fill="{fill}" opacity="{op}"><title>{d["date"]}: {n}</title></rect>')
    for mx, label in month_marks:
        out.append(f'<text x="{mx}" y="{hy + 7 * (cell + gap) + 12}" font-size="9" fill="{c["secondary"]}" letter-spacing="1">{label}</text>')
    # legend, top row, right-aligned with the heatmap
    lx = hx + 52 * (cell + gap) - 2 - 5 * 13 - 34
    out.append(f'<text x="{lx - 6}" y="{hy - 8}" font-size="9" fill="{c["secondary"]}" letter-spacing="1" text-anchor="end">LESS</text>')
    for i, op in enumerate([None, 0.3, 0.55, 0.8, 1.0]):
        fill = c["empty"] if op is None else c["accent"]
        out.append(f'<rect x="{lx + i * 13}" y="{hy - 16}" width="{cell}" height="{cell}" rx="2" fill="{fill}" opacity="{op or 1}"/>')
    out.append(f'<text x="{lx + 5 * 13 + 4}" y="{hy - 8}" font-size="9" fill="{c["secondary"]}" letter-spacing="1">MORE</text>')
    out.append("</svg>\n")
    return "\n".join(out)


def main():
    user = mock() if "--mock" in sys.argv else fetch()
    s = compute(user)
    OUT.mkdir(parents=True, exist_ok=True)
    for theme in THEMES:
        (OUT / f"stats-{theme}.svg").write_text(render(theme, s), encoding="utf-8")
    print(json.dumps({k: v for k, v in s.items() if k != "weeks"}, indent=2, default=str))


if __name__ == "__main__":
    main()

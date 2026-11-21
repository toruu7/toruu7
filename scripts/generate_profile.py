#!/usr/bin/env python3
"""
Self-hosted Living Identity SVG & README generator for @toruu7.
Generates dual-mode (dark Catppuccin Mocha / Aurora & light Catppuccin Latte) SVGs:
  - assets/hero-{dark,light}.svg       (3D dot-matrix wordmark + circular radar halftone avatar + KPIs)
  - assets/highlights-{dark,light}.svg (Current Focus 3-column card)
  - assets/stack-{dark,light}.svg      (Technology Spectrum 4-column language grid)
  - assets/stats-{dark,light}.svg      (Profile Signal 4-column KPI card)
  - assets/heatmap-{dark,light}.svg    (Contribution Energy dot-matrix starfield)
  - assets/social-{dark,light}.svg     (Direct Coordinates contact bar)
And updates README.md with live stats and streak metrics.
"""

from __future__ import annotations

import html
import io
import math
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from PIL import Image, ImageEnhance, ImageOps

USERNAME = "toruu7"
DISPLAY_NAME = "Toru"
ROLE_LINE = "Automation Engineer & Systems Builder"
CREED = "If it is tedious, automate it. If it is sluggish, rebuild it in Rust. If it lacks feel, give it physics."
STACK_LINE = "Rust / Kotlin / TypeScript / Python"
WEBSITE = "https://toru7.dev"
X_URL = "https://x.com/toruuzumi"
X_HANDLE = "@toruuzumi"
LINKEDIN_URL = "https://linkedin.com/in/muhtadee-taron-b4253628b"
EMAIL = "sheikh.taron@northsouth.edu"

ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = ROOT / "assets"

THEMES: dict[str, dict[str, str]] = {
    "dark": {
        "bg_start": "#0a0d16",
        "bg_end": "#111424",
        "border": "#262c44",
        "grid": "#1a2036",
        "dash": "#252c45",
        "accent": "#89b4fa",       # Catppuccin Mocha Blue
        "accent2": "#cba6f7",      # Catppuccin Mocha Mauve
        "accent_soft": "#3b4d7a",
        "text": "#eef2ff",
        "text_sub": "#a6adc8",
        "text_muted": "#6c7086",
        "bar_bg": "#1e2338",
        "tile_bg": "#161a2b",
        "dot_zero": "#1d2338",
        "dot_1": "#2f4373",
        "dot_2": "#4c6cb8",
        "dot_3": "#749bf2",
        "dot_4": "#cba6f7",
        "portrait_dot": "#dce4ff",
    },
    "light": {
        "bg_start": "#fafbfe",
        "bg_end": "#eff1f5",
        "border": "#ccd0da",
        "grid": "#dce0e8",
        "dash": "#bcc0cc",
        "accent": "#1e66f5",       # Catppuccin Latte Blue
        "accent2": "#8839ef",      # Catppuccin Latte Mauve
        "accent_soft": "#99b8f9",
        "text": "#1e1e2e",
        "text_sub": "#4c4f69",
        "text_muted": "#7c7f93",
        "bar_bg": "#dce0e8",
        "tile_bg": "#e6e9ef",
        "dot_zero": "#dce0e8",
        "dot_1": "#acc6fb",
        "dot_2": "#6f9df7",
        "dot_3": "#1e66f5",
        "dot_4": "#8839ef",
        "portrait_dot": "#1e1e2e",
    },
}

LANG_META: dict[str, tuple[str, str]] = {
    "Rust": ("RS", "#fab387"),
    "TypeScript": ("TS", "#89b4fa"),
    "JavaScript": ("JS", "#f9e2af"),
    "Python": ("PY", "#74c7ec"),
    "Kotlin": ("KT", "#cba6f7"),
    "Dart": ("DT", "#94e2d5"),
    "Java": ("JV", "#eba0ac"),
    "C": ("C", "#a6adc8"),
    "C++": ("C+", "#f38ba8"),
    "HTML": ("HT", "#fab387"),
    "CSS": ("CS", "#89dceb"),
    "Shell": ("SH", "#a6e3a1"),
    "Go": ("GO", "#89dceb"),
    "Vue": ("VU", "#a6e3a1"),
}

# 7x7 dot-matrix glyphs for "TORU"
BITMAP_FONT: dict[str, list[str]] = {
    "T": [
        "1111111",
        "1111111",
        "0001100",
        "0001100",
        "0001100",
        "0001100",
        "0001100",
    ],
    "O": [
        "0111110",
        "1111111",
        "1100011",
        "1100011",
        "1100011",
        "1111111",
        "0111110",
    ],
    "R": [
        "1111110",
        "1111111",
        "1100011",
        "1111110",
        "1101100",
        "1100110",
        "1100011",
    ],
    "U": [
        "1100011",
        "1100011",
        "1100011",
        "1100011",
        "1100011",
        "1111111",
        "0111110",
    ],
}


def get_github_token() -> str:
    for env_key in ("GITHUB_TOKEN", "GH_TOKEN"):
        val = os.environ.get(env_key, "").strip()
        if val:
            return val
    try:
        proc = subprocess.run(
            ["git", "credential", "fill"],
            input="protocol=https\nhost=github.com\n\n",
            text=True,
            capture_output=True,
            timeout=5,
            check=False,
        )
        for line in proc.stdout.splitlines():
            if line.startswith("password="):
                return line.split("=", 1)[1].strip()
    except Exception:
        pass
    raise RuntimeError("No GitHub token found in GITHUB_TOKEN/GH_TOKEN or git credential helper.")


def fetch_github_data(token: str) -> dict[str, Any]:
    query = """
    query($login: String!) {
      user(login: $login) {
        login
        avatarUrl(size: 320)
        followers { totalCount }
        repositories(first: 100, ownerAffiliations: OWNER, privacy: PUBLIC, isFork: false) {
          totalCount
          nodes {
            name
            stargazerCount
            languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
              edges {
                size
                node {
                  name
                  color
                }
              }
            }
          }
        }
        contributionsCollection {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                contributionCount
                date
              }
            }
          }
        }
      }
    }
    """
    resp = requests.post(
        "https://api.github.com/graphql",
        json={"query": query, "variables": {"login": USERNAME}},
        headers={
            "Authorization": f"Bearer {token}",
            "User-Agent": "toruu7-profile-generator",
        },
        timeout=20,
    )
    resp.raise_for_status()
    payload = resp.json()
    if "errors" in payload:
        raise RuntimeError(f"GraphQL errors: {payload['errors']}")

    user = payload["data"]["user"]
    repos = user["repositories"]["nodes"]
    total_stars = sum(r["stargazerCount"] for r in repos)

    lang_bytes: dict[str, int] = {}
    for r in repos:
        for edge in r["languages"]["edges"]:
            name = edge["node"]["name"]
            lang_bytes[name] = lang_bytes.get(name, 0) + edge["size"]

    total_bytes = sum(lang_bytes.values()) or 1
    sorted_langs = sorted(lang_bytes.items(), key=lambda kv: kv[1], reverse=True)
    top_langs = [
        {"name": name, "pct": round((size / total_bytes) * 100, 1)}
        for name, size in sorted_langs[:8]
    ]

    cal = user["contributionsCollection"]["contributionCalendar"]
    weeks = cal["weeks"]
    all_days = [d for w in weeks for d in w["contributionDays"]]
    active_days = sum(1 for d in all_days if d["contributionCount"] > 0)

    # Current streak (walk backwards from today; allow today == 0 if yesterday > 0)
    current_streak = 0
    for idx in range(len(all_days) - 1, -1, -1):
        cnt = all_days[idx]["contributionCount"]
        if cnt > 0:
            current_streak += 1
        elif idx == len(all_days) - 1:
            continue
        else:
            break

    return {
        "login": user["login"],
        "avatar_url": user["avatarUrl"],
        "public_repos": user["repositories"]["totalCount"],
        "stars": total_stars,
        "followers": user["followers"]["totalCount"],
        "contributions": cal["totalContributions"],
        "weeks": weeks,
        "active_days": active_days,
        "current_streak": current_streak,
        "top_langs": top_langs,
    }


def fetch_avatar_image(url: str) -> Image.Image:
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    return Image.open(io.BytesIO(resp.content)).convert("L")


def svg_card_shell(
    width: int,
    height: int,
    theme: dict[str, str],
    uid: str,
    inner: str,
    extra_defs: str = "",
    extra_css: str = "",
) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none">
  <defs>
    <linearGradient id="bg-{uid}" x1="0" y1="0" x2="{width}" y2="{height}" gradientUnits="userSpaceOnUse">
      <stop offset="0%" stop-color="{theme['bg_start']}"/>
      <stop offset="100%" stop-color="{theme['bg_end']}"/>
    </linearGradient>
    <pattern id="grid-{uid}" width="28" height="28" patternUnits="userSpaceOnUse">
      <path d="M 28 0 L 0 0 0 28" fill="none" stroke="{theme['grid']}" stroke-width="0.75" opacity="0.5"/>
    </pattern>
    <clipPath id="clip-{uid}">
      <rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="16"/>
    </clipPath>
    {extra_defs}
  </defs>
  <style>
    .mono {{ font-family: 'JetBrains Mono', 'Fira Code', ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }}
    .sans {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Inter, Helvetica, Arial, sans-serif; }}
    .kicker {{ font-size: 10.5px; letter-spacing: 2.6px; fill: {theme['accent']}; font-weight: 600; }}
    .title {{ font-size: 21px; fill: {theme['text']}; font-weight: 600; }}
    .muted {{ fill: {theme['text_muted']}; }}
    .sub {{ fill: {theme['text_sub']}; }}
    {extra_css}
  </style>
  <g clip-path="url(#clip-{uid})">
    <rect x="0" y="0" width="{width}" height="{height}" fill="url(#bg-{uid})"/>
    <rect x="0" y="0" width="{width}" height="{height}" fill="url(#grid-{uid})"/>
    {inner}
  </g>
  <rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="16" stroke="{theme['border']}" stroke-width="1"/>
</svg>
"""


def build_wordmark_dots(word: str, start_x: float, start_y: float, step: float, theme: dict[str, str]) -> str:
    parts: list[str] = []
    cx_cursor = start_x
    for li, ch in enumerate(word.upper()):
        grid = BITMAP_FONT.get(ch)
        if not grid:
            cx_cursor += step * 4
            continue
        for r_idx, row in enumerate(grid):
            for c_idx, cell in enumerate(row):
                if cell != "1":
                    continue
                x = cx_cursor + c_idx * step
                y = start_y + r_idx * step
                # 3D extruded shadow dot
                parts.append(
                    f'<circle cx="{x + 3.5:.1f}" cy="{y + 3.5:.1f}" r="3.1" fill="{theme["accent"]}" opacity="0.34"/>'
                )
                # Secondary mauve depth dot
                parts.append(
                    f'<circle cx="{x + 1.8:.1f}" cy="{y + 1.8:.1f}" r="3.0" fill="{theme["accent2"]}" opacity="0.22"/>'
                )
                # Crisp foreground dot
                delay = ((li * 7 + c_idx + r_idx) % 12) * 0.18
                parts.append(
                    f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.1" fill="{theme["text"]}" class="wm-dot" style="animation-delay:{delay:.2f}s"/>'
                )
        cx_cursor += (len(grid[0]) + 1.8) * step
    return "\n    ".join(parts)


def build_portrait_dots(
    img_gray: Image.Image,
    cx: float,
    cy: float,
    radius: float,
    mode: str,
    theme: dict[str, str],
) -> str:
    size = 48
    img = ImageOps.fit(img_gray, (size, size), method=Image.Resampling.LANCZOS)
    img = ImageOps.autocontrast(img, cutoff=2)
    img = ImageEnhance.Contrast(img).enhance(1.35)
    pixels = img.load()

    step = (radius * 2) / size
    left = cx - radius + step / 2
    top = cy - radius + step / 2

    dots: list[str] = []
    for y in range(size):
        for x in range(size):
            px = left + x * step
            py = top + y * step
            dist = math.hypot(px - cx, py - cy)
            if dist > radius - 2:
                continue
            lum = pixels[x, y] / 255.0
            if mode == "light":
                intensity = 1.0 - lum
            else:
                intensity = lum
            # Edge feathering inside the circular radar
            edge_fade = max(0.0, min(1.0, (radius - dist) / 14.0))
            val = intensity * edge_fade
            if val < 0.09:
                continue
            r = 0.55 + (val ** 1.15) * 1.85
            op = 0.16 + val * 0.82
            dots.append(
                f'<circle cx="{px:.1f}" cy="{py:.1f}" r="{r:.2f}" fill="{theme["portrait_dot"]}" opacity="{op:.2f}"/>'
            )
    return "\n    ".join(dots)


def render_hero(data: dict[str, Any], avatar: Image.Image, mode: str, theme: dict[str, str]) -> str:
    w, h = 900, 440
    uid = f"hero-{mode}"
    extra_defs = f"""
    <radialGradient id="aurora-{uid}" cx="75%" cy="46%" r="36%">
      <stop offset="0%" stop-color="{theme['accent']}" stop-opacity="0.22"/>
      <stop offset="55%" stop-color="{theme['accent2']}" stop-opacity="0.08"/>
      <stop offset="100%" stop-color="{theme['bg_end']}" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="aurora-left-{uid}" cx="22%" cy="42%" r="34%">
      <stop offset="0%" stop-color="{theme['accent2']}" stop-opacity="0.12"/>
      <stop offset="100%" stop-color="{theme['bg_start']}" stop-opacity="0"/>
    </radialGradient>
    <clipPath id="radar-clip-{uid}">
      <circle cx="680" cy="198" r="128"/>
    </clipPath>
    """
    extra_css = """
    @keyframes pulseDot { 0%, 100% { opacity: 0.96; } 50% { opacity: 0.62; } }
    @keyframes spinSlow { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
    @keyframes scanMove { 0% { transform: translateY(-120px); opacity: 0; } 15% { opacity: 0.45; } 85% { opacity: 0.45; } 100% { transform: translateY(120px); opacity: 0; } }
    .wm-dot { animation: pulseDot 4.2s ease-in-out infinite; }
    .radar-spin { transform-origin: 680px 198px; animation: spinSlow 42s linear infinite; }
    .scan-bar { animation: scanMove 6s ease-in-out infinite; }
    """

    wordmark = build_wordmark_dots(DISPLAY_NAME, start_x=52, start_y=124, step=12.5, theme=theme)
    portrait = build_portrait_dots(avatar, cx=680, cy=198, radius=124, mode=mode, theme=theme)

    kpis = [
        ("REPOSITORIES", f"{data['public_repos']:,}"),
        ("STARS", f"{data['stars']:,}"),
        ("CONTRIBUTIONS", f"{data['contributions']:,}"),
        ("FOLLOWERS", f"{data['followers']:,}"),
    ]
    kpi_svg: list[str] = []
    xs = [52, 266, 480, 694]
    for i, (label, val) in enumerate(kpis):
        x = xs[i]
        kpi_svg.append(
            f'<text x="{x}" y="376" class="mono muted" font-size="10" letter-spacing="2">{label}</text>'
            f'<text x="{x}" y="406" class="mono" font-size="22" font-weight="600" fill="{theme["text"]}">{val}</text>'
        )
        if i < len(kpis) - 1:
            dot_x = x + 178
            kpi_svg.append(
                f'<circle cx="{dot_x}" cy="388" r="2.6" fill="{theme["accent"]}" opacity="0.85"/>'
            )

    inner = f"""
    <rect x="0" y="0" width="{w}" height="{h}" fill="url(#aurora-{uid})"/>
    <rect x="0" y="0" width="{w}" height="{h}" fill="url(#aurora-left-{uid})"/>

    <!-- Top meta bar -->
    <text x="52" y="38" class="mono muted" font-size="10.5" letter-spacing="2.8">TORU / LIVING IDENTITY</text>
    <text x="848" y="38" text-anchor="end" class="mono muted" font-size="11">@{USERNAME}</text>

    <!-- Left identity column -->
    <text x="52" y="96" class="mono kicker">HELLO, WORLD. I&apos;M</text>
    {wordmark}
    <text x="52" y="266" class="mono" font-size="14" fill="{theme['text']}">{html.escape(STACK_LINE)}</text>
    <text x="52" y="292" class="mono muted" font-size="12">{html.escape(ROLE_LINE)}</text>

    <!-- Right radar + halftone portrait -->
    <circle cx="680" cy="198" r="142" stroke="{theme['accent']}" stroke-width="1" stroke-dasharray="3 7" opacity="0.38" class="radar-spin"/>
    <circle cx="680" cy="198" r="131" stroke="{theme['accent']}" stroke-width="0.9" opacity="0.28"/>
    <line x1="538" y1="198" x2="554" y2="198" stroke="{theme['accent']}" stroke-width="1" opacity="0.4"/>
    <line x1="806" y1="198" x2="822" y2="198" stroke="{theme['accent']}" stroke-width="1" opacity="0.4"/>
    <line x1="680" y1="56" x2="680" y2="72" stroke="{theme['accent']}" stroke-width="1" opacity="0.4"/>
    <line x1="680" y1="324" x2="680" y2="340" stroke="{theme['accent']}" stroke-width="1" opacity="0.4"/>
    {portrait}
    <g clip-path="url(#radar-clip-{uid})">
      <line x1="550" y1="198" x2="810" y2="198" stroke="{theme['accent']}" stroke-width="1.4" class="scan-bar"/>
    </g>

    <!-- Bottom divider + KPI row -->
    <line x1="52" y1="348" x2="848" y2="348" stroke="{theme['dash']}" stroke-width="1" stroke-dasharray="3 7"/>
    {''.join(kpi_svg)}
    """
    return svg_card_shell(w, h, theme, uid, inner, extra_defs=extra_defs, extra_css=extra_css)


def render_highlights(mode: str, theme: dict[str, str]) -> str:
    w, h = 900, 215
    uid = f"highlights-{mode}"
    items = [
        ("01", "Automation & Pipelines", "Current focus"),
        ("02", "Local-First AI Runtimes", "In the build queue"),
        ("03", "Gesture & Mobile Systems", "In the build queue"),
    ]
    cols: list[str] = []
    xs = [48, 330, 612]
    for (num, heading, status), x in zip(items, xs):
        cols.append(
            f'<text x="{x}" y="128" class="mono kicker">{num}</text>'
            f'<text x="{x}" y="156" class="sans" font-size="16" font-weight="600" fill="{theme["text"]}">{html.escape(heading)}</text>'
            f'<text x="{x}" y="180" class="mono muted" font-size="11.5">{html.escape(status)}</text>'
        )
    inner = f"""
    <text x="48" y="42" class="mono kicker">CURRENT FOCUS</text>
    <text x="48" y="72" class="mono title">Ideas taking shape</text>
    <line x1="48" y1="92" x2="852" y2="92" stroke="{theme['dash']}" stroke-width="1" stroke-dasharray="4 8"/>
    {''.join(cols)}
    """
    return svg_card_shell(w, h, theme, uid, inner)


def render_stack(data: dict[str, Any], mode: str, theme: dict[str, str]) -> str:
    langs = data["top_langs"][:8]
    rows = 2 if len(langs) > 4 else 1
    w = 900
    h = 225 if rows == 1 else 320
    uid = f"stack-{mode}"

    cards: list[str] = []
    col_xs = [48, 255, 462, 669]
    row_ys = [122, 224]
    bar_w = 172

    for idx, item in enumerate(langs):
        name = item["name"]
        pct = item["pct"]
        abbr, color = LANG_META.get(name, (name[:2].upper(), theme["accent"]))
        x = col_xs[idx % 4]
        y = row_ys[idx // 4]
        fill_w = max(6.0, (min(pct, 100.0) / 100.0) * bar_w)

        cards.append(f"""
        <rect x="{x}" y="{y}" width="30" height="30" rx="7" fill="{theme['tile_bg']}" stroke="{color}" stroke-width="1.2" stroke-opacity="0.7"/>
        <text x="{x + 15}" y="{y + 19}" text-anchor="middle" class="mono" font-size="11" font-weight="700" fill="{color}">{html.escape(abbr)}</text>
        <text x="{x}" y="{y + 52}" class="mono" font-size="13.5" font-weight="600" fill="{theme['text']}">{html.escape(name)}</text>
        <text x="{x}" y="{y + 70}" class="mono muted" font-size="11">{pct:.1f}% of public code</text>
        <rect x="{x}" y="{y + 80}" width="{bar_w}" height="3" rx="1.5" fill="{theme['bar_bg']}"/>
        <rect x="{x}" y="{y + 80}" width="{fill_w:.1f}" height="3" rx="1.5" fill="{color}"/>
        """)

    inner = f"""
    <text x="48" y="42" class="mono kicker">TECHNOLOGY SPECTRUM</text>
    <text x="48" y="72" class="mono title">The tools behind the work</text>
    <line x1="48" y1="92" x2="852" y2="92" stroke="{theme['dash']}" stroke-width="1" stroke-dasharray="4 8"/>
    {''.join(cards)}
    """
    return svg_card_shell(w, h, theme, uid, inner)


def render_stats(data: dict[str, Any], mode: str, theme: dict[str, str]) -> str:
    w, h = 900, 232
    uid = f"stats-{mode}"
    kpis = [
        ("REPOSITORIES", f"{data['public_repos']:,}"),
        ("STARS", f"{data['stars']:,}"),
        ("CONTRIBUTIONS", f"{data['contributions']:,}"),
        ("FOLLOWERS", f"{data['followers']:,}"),
    ]
    xs = [48, 256, 464, 672]
    cols: list[str] = []
    for (label, val), x in zip(kpis, xs):
        cols.append(f"""
        <text x="{x}" y="142" class="mono" font-size="26" font-weight="700" fill="{theme['text']}">{val}</text>
        <text x="{x}" y="164" class="mono muted" font-size="10" letter-spacing="2">{label}</text>
        <circle cx="{x + 6}" cy="194" r="6" fill="{theme['accent']}" fill-opacity="0.24" stroke="{theme['accent']}" stroke-width="1.2"/>
        <line x1="{x + 20}" y1="194" x2="{x + 168}" y2="194" stroke="{theme['dash']}" stroke-width="1" stroke-dasharray="4 8"/>
        """)
    inner = f"""
    <text x="48" y="42" class="mono kicker">PROFILE SIGNAL</text>
    <text x="48" y="72" class="mono title">Momentum, made visible</text>
    <line x1="48" y1="92" x2="852" y2="92" stroke="{theme['dash']}" stroke-width="1" stroke-dasharray="4 8"/>
    {''.join(cols)}
    """
    return svg_card_shell(w, h, theme, uid, inner)


def render_heatmap(data: dict[str, Any], mode: str, theme: dict[str, str]) -> str:
    w, h = 900, 296
    uid = f"heatmap-{mode}"
    weeks = data["weeks"][-48:]  # 48 clean columns spanning the card

    counts = [d["contributionCount"] for wk in weeks for d in wk["contributionDays"]]
    max_c = max(counts) if counts else 1

    start_x = 56.0
    start_y = 122.0
    col_gap = (844.0 - start_x) / max(1, len(weeks) - 1)
    row_gap = 18.0

    dots: list[str] = []
    for wi, wk in enumerate(weeks):
        for di, day in enumerate(wk["contributionDays"]):
            cnt = day["contributionCount"]
            cx = start_x + wi * col_gap
            cy = start_y + di * row_gap
            if cnt == 0:
                r = 2.0
                color = theme["dot_zero"]
                op = 0.72
            else:
                ratio = cnt / max_c
                if ratio < 0.25:
                    r, color, op = 2.8, theme["dot_1"], 0.85
                elif ratio < 0.5:
                    r, color, op = 3.5, theme["dot_2"], 0.92
                elif ratio < 0.78:
                    r, color, op = 4.3, theme["dot_3"], 0.96
                else:
                    r, color, op = 5.1, theme["dot_4"], 1.0
            dots.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{color}" opacity="{op:.2f}"/>')

    inner = f"""
    <text x="48" y="42" class="mono kicker">CONTRIBUTION ENERGY</text>
    <text x="48" y="72" class="mono title">Every day leaves a trace</text>
    <line x1="48" y1="92" x2="852" y2="92" stroke="{theme['dash']}" stroke-width="1" stroke-dasharray="4 8"/>
    {''.join(dots)}
    <text x="48" y="268" class="mono muted" font-size="11">{data['contributions']:,} contributions · brighter stars mark busier days</text>
    <line x1="774" y1="264" x2="852" y2="264" stroke="{theme['accent']}" stroke-width="2" stroke-linecap="round" opacity="0.75"/>
    """
    return svg_card_shell(w, h, theme, uid, inner)


def render_social(mode: str, theme: dict[str, str]) -> str:
    w, h = 900, 126
    uid = f"social-{mode}"
    nodes = [
        ("WEBSITE", "toru7.dev"),
        ("X / TWITTER", X_HANDLE),
        ("GITHUB", f"@{USERNAME}"),
        ("LINKEDIN", DISPLAY_NAME),
    ]
    xs = [48, 256, 464, 672]
    cols: list[str] = []
    for (k, v), x in zip(nodes, xs):
        cols.append(f"""
        <circle cx="{x + 4}" cy="50" r="3" fill="{theme['accent']}"/>
        <text x="{x + 16}" y="54" class="mono muted" font-size="10" letter-spacing="2">{k}</text>
        <text x="{x}" y="86" class="mono" font-size="15" font-weight="600" fill="{theme['text']}">{html.escape(v)}</text>
        """)
    inner = f"""
    <line x1="48" y1="24" x2="852" y2="24" stroke="{theme['dash']}" stroke-width="1" stroke-dasharray="4 8"/>
    {''.join(cols)}
    """
    return svg_card_shell(w, h, theme, uid, inner)


def render_readme(data: dict[str, Any]) -> str:
    top_names = " · ".join(item["name"] for item in data["top_langs"][:6])
    return f"""<div align="center">

<p><sub>LIVING IDENTITY · {DISPLAY_NAME.upper()} · LIVE</sub></p>

<picture>
  <source media="(prefers-color-scheme: light)" srcset="assets/hero-light.svg" />
  <img src="assets/hero-dark.svg" width="100%" alt="{DISPLAY_NAME} animated Living Identity portrait and 3D dot-matrix wordmark" />
</picture>

<p><strong>{ROLE_LINE}</strong></p>
<p>{CREED}</p>
<p>
  <a href="{WEBSITE}">Website</a> &nbsp;·&nbsp;
  <a href="{X_URL}">X ({X_HANDLE})</a> &nbsp;·&nbsp;
  <a href="{LINKEDIN_URL}">LinkedIn</a> &nbsp;·&nbsp;
  <a href="mailto:{EMAIL}">Email</a>
</p>

</div>

<p align="center"><sub>✦ ───────────────────────────── ✦</sub></p>

<h2>Identity, with signal</h2>

<table width="100%">
  <tbody>
    <tr>
      <td width="62%">
        <p>{CREED}</p>
        <p><strong>Focus:</strong> <code>Rust</code> · <code>Kotlin</code> · <code>TypeScript</code> · <code>Python</code></p>
        <p><sub>Engineering high-throughput automation pipelines by day. Architecting local-first AI runtimes and gesture-driven systems by night.</sub></p>
      </td>
      <td width="38%">
        <p><code>LIVE SIGNAL</code></p>
        <p>
          <strong>{data['public_repos']:,}</strong> public repos<br/>
          <strong>{data['stars']:,}</strong> stars<br/>
          <strong>{data['contributions']:,}</strong> contributions (1y)<br/>
          <strong>{data['followers']:,}</strong> followers
        </p>
      </td>
    </tr>
  </tbody>
</table>

<p align="center"><sub>✦ ───────────────────────────── ✦</sub></p>

<h2>What moves the work</h2>

<picture>
  <source media="(prefers-color-scheme: light)" srcset="assets/highlights-light.svg" />
  <img src="assets/highlights-dark.svg" width="100%" alt="{DISPLAY_NAME} current focus highlights" />
</picture>

<p align="center"><sub>Positioning is useful when the proof is close behind it.</sub></p>

<p align="center"><sub>✦ ───────────────────────────── ✦</sub></p>

<h2>The tools behind the signal</h2>

<picture>
  <source media="(prefers-color-scheme: light)" srcset="assets/stack-light.svg" />
  <img src="assets/stack-dark.svg" width="100%" alt="{DISPLAY_NAME} technology spectrum" />
</picture>

<p align="center"><sub>{top_names} · chosen for the work, not the trend</sub></p>

<p align="center"><sub>✦ ───────────────────────────── ✦</sub></p>

<h2>Momentum, made visible</h2>

<picture>
  <source media="(prefers-color-scheme: light)" srcset="assets/stats-light.svg" />
  <img src="assets/stats-dark.svg" width="100%" alt="{DISPLAY_NAME} live GitHub signal" />
</picture>

<p align="center"><sub>✦ ───────────────────────────── ✦</sub></p>

<h2>The trail behind the work</h2>

<picture>
  <source media="(prefers-color-scheme: light)" srcset="assets/heatmap-light.svg" />
  <img src="assets/heatmap-dark.svg" width="100%" alt="{DISPLAY_NAME} contribution energy field" />
</picture>

<p align="center"><sub>{data['current_streak']} day current streak · {data['active_days']} active days</sub></p>

<p align="center"><sub>✦ ───────────────────────────── ✦</sub></p>

<div align="center">

<p><sub>KEEP THE SIGNAL MOVING</sub></p>
<h2>Make something worth noticing</h2>
<p>I like working with people who care about craft, context, and shipping the useful version.</p>

<picture>
  <source media="(prefers-color-scheme: light)" srcset="assets/social-light.svg" />
  <img src="assets/social-dark.svg" width="100%" alt="{DISPLAY_NAME} direct coordinates" />
</picture>

<p>
  <a href="{WEBSITE}">Website</a> &nbsp;·&nbsp;
  <a href="{X_URL}">X</a> &nbsp;·&nbsp;
  <a href="{LINKEDIN_URL}">LinkedIn</a> &nbsp;·&nbsp;
  <a href="mailto:{EMAIL}">Email</a>
</p>

</div>
"""


def main() -> None:
    token = get_github_token()
    data = fetch_github_data(token)
    avatar = fetch_avatar_image(data["avatar_url"])

    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    for mode, theme in THEMES.items():
        (ASSETS_DIR / f"hero-{mode}.svg").write_text(
            render_hero(data, avatar, mode, theme), encoding="utf-8"
        )
        (ASSETS_DIR / f"highlights-{mode}.svg").write_text(
            render_highlights(mode, theme), encoding="utf-8"
        )
        (ASSETS_DIR / f"stack-{mode}.svg").write_text(
            render_stack(data, mode, theme), encoding="utf-8"
        )
        (ASSETS_DIR / f"stats-{mode}.svg").write_text(
            render_stats(data, mode, theme), encoding="utf-8"
        )
        (ASSETS_DIR / f"heatmap-{mode}.svg").write_text(
            render_heatmap(data, mode, theme), encoding="utf-8"
        )
        (ASSETS_DIR / f"social-{mode}.svg").write_text(
            render_social(mode, theme), encoding="utf-8"
        )

    (ROOT / "README.md").write_text(render_readme(data), encoding="utf-8")
    print(
        f"Generated 12 SVGs and README.md for @{USERNAME} "
        f"({data['public_repos']} repos, {data['stars']} stars, "
        f"{data['contributions']} contribs, {data['current_streak']}d streak)."
    )


if __name__ == "__main__":
    main()

"""data/articles.json → site/index.html + site/data/feed.json

프론트는 빌드된 정적 HTML 한 장이다. 별도 서버/DB 없이 GitHub Pages에 올린다.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import config
import processor

log = logging.getLogger("build_site")
FEED_DATA_PLACEHOLDER = "__FEED_DATA__"


def lean_item(item: dict) -> dict:
    comments = []
    for index, comment in enumerate(item.get("comments") or []):
        translations = item.get("comments_ko") or []
        comments.append(
            {
                "author": comment.get("author", ""),
                "score": comment.get("score", 0),
                "body": comment.get("body", ""),
                "body_ko": translations[index] if index < len(translations) else "",
            }
        )

    body_ko = (item.get("body_ko") or "").strip()
    if not item.get("translated"):
        body_ko = body_ko[:6000]

    summary_ko = item.get("summary_ko") or ""
    if item.get("original_only"):
        summary_ko = ""

    return {
        "id": item["id"],
        "source": item["source"],
        "source_label": item.get("source_label") or item["source"],
        "kind": item.get("kind", "news"),
        "title": item.get("title", ""),
        "title_ko": item.get("title_ko") or item.get("title", ""),
        "summary_ko": summary_ko,
        "body_ko": body_ko,
        "url": item.get("url", ""),
        "published": item.get("published"),
        "author": item.get("author", ""),
        "image": item.get("image"),
        "team_ids": item.get("team_ids") or [],
        "team_names": item.get("team_names") or [],
        "tags": item.get("tags") or [],
        "match": item.get("match"),
        "hot": bool(item.get("hot")),
        "comments": comments,
        "translated": bool(item.get("translated")),
        "original_only": bool(item.get("original_only")),
        "history": bool(item.get("history")),
        "priority": item.get("priority", 0),
        "video_channel": item.get("video_channel"),
        "video_team": item.get("video_team"),
    }


def build_payload(items: list[dict], stats: dict | None = None) -> dict:
    now = datetime.now(timezone.utc)
    focus = set(config.FOCUS_TEAM_IDS)
    items = [
        item
        for item in items
        if item.get("video_team") in focus
        or any(team in focus for team in item.get("team_ids") or [])
        or item.get("source") in config.FOCUS_SOURCES
    ]
    sources = {
        key: {"label": meta["label"], "color": meta["color"]}
        for key, meta in config.SOURCES.items()
    }

    recent_matches = []
    if config.MATCHES_FILE.exists():
        try:
            raw_matches = json.loads(config.MATCHES_FILE.read_text(encoding="utf-8"))
        except ValueError:
            raw_matches = []
        for match in raw_matches if isinstance(raw_matches, list) else []:
            if match.get("home") not in config.FOCUS_TEAM_IDS and match.get("away") not in config.FOCUS_TEAM_IDS:
                continue
            finished = processor.parse_dt(match.get("finished_at"))
            if not finished:
                continue
            recent_matches.append(
                {
                    "home": match.get("home"),
                    "away": match.get("away"),
                    "score": match.get("score", ""),
                    "finished_at": match.get("finished_at"),
                    "round": match.get("round"),
                }
            )
        recent_matches.sort(key=lambda item: item["finished_at"], reverse=True)

    referenced_team_ids = set(focus)
    for match in recent_matches[:6]:
        referenced_team_ids.update((match.get("home"), match.get("away")))
    for item in items:
        referenced_team_ids.add(item.get("video_team"))
        referenced_team_ids.update(item.get("team_ids") or [])
    referenced_team_ids.discard(None)

    return {
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "timezone": config.TIMEZONE,
        "match_priority_hours": config.MATCH_PRIORITY_HOURS,
        "stats": stats or {},
        "sources": sources,
        "tags": config.TAG_ORDER,
        "focus_team_ids": config.FOCUS_TEAM_IDS,
        "teams": [
            {"id": team["id"], "ko": team["ko"], "it": team["it"], "color": team["color"]}
            for team in config.TEAMS
            if team["id"] in referenced_team_ids
        ],
        "recent_matches": recent_matches[:6],
        "items": [lean_item(item) for item in items],
    }


def build(items: list[dict], stats: dict | None = None) -> Path:
    payload = build_payload(items, stats)

    site_data_dir = config.SITE_DIR / "data"
    site_data_dir.mkdir(parents=True, exist_ok=True)
    (site_data_dir / "feed.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    template = (config.TEMPLATE_DIR / "index.html").read_text(encoding="utf-8")
    data_js = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = template.replace(FEED_DATA_PLACEHOLDER, data_js)

    out = config.SITE_DIR / "index.html"
    out.write_text(html, encoding="utf-8")

    # GitHub Pages에서 data 폴더가 그대로 서빙되도록 .nojekyll
    (config.SITE_DIR / ".nojekyll").write_text("", encoding="utf-8")

    log.info("사이트 생성: %s (%s개 기사, %.1f KB)", out, len(items), out.stat().st_size / 1024)
    return out


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    payload = json.loads(config.ARTICLES_FILE.read_text(encoding="utf-8"))
    build(payload.get("articles", []), payload.get("stats", {}))

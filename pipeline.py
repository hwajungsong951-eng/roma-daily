"""수집 → 번역 → 병합 → 정적 사이트 생성.

사용법:
    python pipeline.py                 # 전체 실행
    python pipeline.py --limit 5       # 처음 5개만 (API 비용 테스트)
    python pipeline.py --no-fetch      # 저장된 data/raw.json 재사용

GitHub Actions에서는 하루 두 번 이 스크립트를 실행한다.
"""
from __future__ import annotations

import argparse
import json
import logging
import re
from datetime import datetime, timedelta, timezone

import build_site
import config
import fetcher
import fixtures
import processor

log = logging.getLogger("pipeline")


def load_previous() -> list[dict]:
    if not config.ARTICLES_FILE.exists():
        return []
    try:
        payload = json.loads(config.ARTICLES_FILE.read_text(encoding="utf-8"))
        return payload.get("articles", [])
    except ValueError:
        log.warning("articles.json 읽기 실패, 새로 시작합니다")
        return []


COLUMN_HINTS = (
    "analisi",
    "analysis",
    "pagelle",
    "ratings",
    "moviola",
    "considerazioni",
    "tactical",
    "tattica",
    "editoriale",
    "editorial",
    "opinion",
    "focus",
    "rubric",
    "primo piano",
    "l'angolo",
    "avversaria",
    "things we learned",
    "talking points",
    "approfondimento",
    "採点",
    "分析",
    "戦術",
    "歴史",
    "コラム",
    "sinners",
    "tifo",
    "curve",
    "boys",
)


def content_group(article: dict) -> str:
    group = config.SOURCE_GROUPS.get(article.get("source", ""), "news")
    if group == "team":
        return "column" if _is_columnish(article) else "news"
    return group


def focus_teams_of(article: dict) -> set[str]:
    source = article.get("source", "")
    if source in ("forzaroma", "romanews", "asroma_blog", "romapress", "chiesaditotti"):
        return {"roma"}
    teams = set(
        processor.detect_teams(
            f"{article.get('title', '')}\n{(article.get('body') or '')[:1500]}"
        )
    )
    if article.get("video_team"):
        teams.add(article["video_team"])
    return teams & set(config.FOCUS_TEAM_IDS)


def is_focus(article: dict) -> bool:
    return bool(focus_teams_of(article))


def _is_serie_a(article: dict) -> bool:
    source = article.get("source", "")
    if source in ("sportellate", "footballitalia", "romapress", "ilmessaggero", "chiesaditotti"):
        return True
    text = f"{article.get('title', '')}\n{(article.get('body') or '')[:1500]}"
    return "serie a" in text.lower() or bool(processor.detect_teams(text))


def _is_columnish(article: dict) -> bool:
    title = article.get("title", "").lower()
    categories = " ".join(article.get("categories") or []).lower()
    text = f"{title} {categories}"
    if any(hint in text for hint in COLUMN_HINTS):
        return True
    return processor.detect_kind(article) == "analysis"


def _is_first_team(article: dict) -> bool:
    title = article.get("title", "").lower()
    return not any(
        word in title
        for word in ("women", "femminile", "primavera", "under 18", "under 15", "u18", "u15", "giovanili", "settore giovanile")
    )


OFFTOPIC_HINTS = (
    "moglie",
    "tradito",
    "amanda",
    "murale",
    "vandal",
    "figc",
    "elezioni",
    "prevendita",
    "info biglietti",
    "biglietti",
    "convocati",
    "probabili formazioni",
    "dove vedere",
)


def _is_offtopic(article: dict) -> bool:
    if article.get("history_hint") or article.get("source") == "history":
        return False
    title = article.get("title", "").lower()
    return any(word in title for word in OFFTOPIC_HINTS)


def _match_key_of(article: dict, matches: list[dict]) -> str | None:
    focus = processor.detect_teams(
        f"{article.get('title', '')}\n{(article.get('body') or '')[:200]}"
    )
    match = processor.find_match(article, focus, matches)
    return processor.match_key(match)


def _is_women_video(article: dict) -> bool:
    title = article.get("title", "").lower()
    return any(word in title for word in ("women", "femminile", "women's", "ladies"))


def _is_non_football(article: dict) -> bool:
    title = article.get("title", "").lower()
    return any(
        word in title
        for word in (
            "rugby",
            "volley",
            "pallavolo",
            "basket",
            "baseball",
            "nuoto",
            "tennis",
            "rally",
            "ciclismo",
            "atletica",
            "hockey",
            "dilettanti",
            "promozione",
            "eccellenza",
            "serie d",
            "top5",
            "fotogallery",
        )
    )


LOCAL_SPORT_SOURCES = {"ilmessaggero"}
FOOTBALL_WORDS = (
    "calcio",
    "serie a",
    "roma",
    "udinese",
    "lazio",
    "inter",
    "juventus",
    "milan",
    "atalanta",
    "fiorentina",
    "torino",
    "como",
    "venezia",
    "genoa",
    "cagliari",
    "bologna",
    "monza",
    "sassuolo",
    "lecce",
    "verona",
    "frosinone",
)


def _is_local_football(article: dict) -> bool:
    if article.get("source") not in LOCAL_SPORT_SOURCES:
        return True
    text = f"{article.get('title', '')} {' '.join(article.get('categories') or [])}".lower()
    return any(word in text for word in FOOTBALL_WORDS)


def _is_match_report(article: dict) -> bool:
    title = article.get("title", "").lower()
    if any(word in title for word in ("probabili formazioni", "dove vedere", "convocati", "prevendita", "info biglietti")):
        return False
    if any(word in title for word in ("diretta", "live", "cronaca", "pagelle", "highlights", "report", "ratings", "match report")):
        return True
    return bool(re.search(r"\b\d{1,2}\s*[-–:]\s*\d{1,2}\b", title))


def _candidate_priority(article: dict, matches: list[dict]) -> float:
    published = processor.parse_dt(article.get("published")) or processor.now_utc()
    focus = processor.detect_teams(
        f"{article.get('title', '')}\n{(article.get('body') or '')[:200]}"
    )
    kind = processor.detect_kind(article)
    match = processor.find_match(article, focus, matches)
    value = processor.compute_priority(article.get("source", ""), kind, match, published, focus, matches)
    value += min(len(article.get("body") or ""), 8000) / 400
    return value


def select_for_run(
    raw: list[dict],
    previous: list[dict],
    quotas: dict[str, int],
    matches: list[dict],
    history_limit: int = config.HISTORY_PER_RUN,
) -> list[dict]:
    """그룹별 쿼터만큼만 골라 번역 비용을 통제한다."""
    done_ids = {
        item["id"]
        for item in previous
        if item.get("translated") or item.get("original_only")
    }
    pool_by_id = {article["id"]: article for article in raw}
    for item in previous:
        if not item.get("translated") and not item.get("original_only"):
            pool_by_id.setdefault(item["id"], item)

    pool = [
        article
        for article in pool_by_id.values()
        if article["id"] not in done_ids
        and is_focus(article)
        and (article.get("source") == "youtube" or _is_first_team(article))
        and not _is_offtopic(article)
        and not _is_non_football(article)
        and _is_local_football(article)
        and not (
            article.get("source") == "reddit"
            and len(article.get("body") or "") < config.REDDIT_MIN_BODY_CHARS
        )
        and (
            article.get("history_hint")
            or article.get("source") == "history"
            or (
                processor.parse_dt(article.get("published"))
                and processor.parse_dt(article.get("published"))
                >= datetime.now(timezone.utc) - timedelta(days=config.FEED_KEEP_DAYS)
            )
        )
    ]
    priority_cache: dict[str, float] = {}

    def score(article: dict) -> float:
        if article["id"] not in priority_cache:
            value = _candidate_priority(article, matches)
            if article.get("history_hint") or config.is_history_text(article.get("title", "")):
                value += 80
            priority_cache[article["id"]] = value
        return priority_cache[article["id"]]

    selected: list[dict] = []
    selected_ids: set[str] = set()

    def take(candidates: list[dict], limit: int) -> int:
        taken = 0
        for article in candidates:
            if taken >= limit:
                break
            if article["id"] in selected_ids:
                continue
            selected.append(article)
            selected_ids.add(article["id"])
            taken += 1
        return taken

    column_quota = quotas.get("column", 0)
    if column_quota:
        column_rank = {
            "ultimouomo": 1,
            "sportellate": 1,
            "sportellate_history": 1,
            "history": 0,
            "forzaroma": 0,
            "romanews": 0,
            "asroma_blog": 0,
            "chiesaditotti": 0,
            "footballitalia": 1,
            "footballzone": 1,
            "footballchannel": 1,
            "gentlemanultra": 1,
            "reddit": 2,
            "romapress": 1,
            "ilmessaggero": 2,
            "guardian": 1,
            "cbssports": 2,
        }
        columns = [
            article
            for article in pool
            if content_group(article) == "column"
            and _is_serie_a(article)
            and len(article.get("body") or "") <= config.MAX_COLUMN_BODY_CHARS
        ]
        columns.sort(
            key=lambda article: (
                column_rank.get(article.get("source", ""), 9),
                len(article.get("body") or "") < config.MIN_COLUMN_BODY_CHARS,
                -score(article),
            )
        )

        # 역사 칼럼은 회차당 최소 1개를 먼저 확보한다.
        history_candidates = [
            article
            for article in columns
            if article.get("history_hint") or config.is_history_text(article.get("title", ""))
        ]
        history_ids = {article["id"] for article in history_candidates}
        history_taken = 0
        for team in config.FOCUS_TEAM_IDS:
            if history_taken >= history_limit:
                break
            team_history = [
                article
                for article in history_candidates
                if article["id"] not in selected_ids and team in focus_teams_of(article)
            ]
            team_history.sort(key=score, reverse=True)
            history_taken += take(team_history, 1)
        history_taken += take(
            [article for article in history_candidates if article["id"] not in selected_ids],
            history_limit - history_taken,
        )
        remaining_columns = [
            article
            for article in columns
            if article["id"] not in selected_ids and article["id"] not in history_ids
        ]
        taken = history_taken

        # 포커스 팀(로마) 칼럼을 우선 확보한다.
        for team in config.FOCUS_TEAM_IDS:
            if taken >= column_quota:
                break
            if any(
                team in focus_teams_of(article)
                for article in selected
                if content_group(article) != "video"
            ):
                continue
            team_columns = [
                article
                for article in remaining_columns
                if article["id"] not in selected_ids and team in focus_teams_of(article)
            ]
            team_columns.sort(
                key=lambda article: (
                    len(article.get("body") or "") < config.MIN_COLUMN_BODY_CHARS,
                    -score(article),
                )
            )
            taken += take(team_columns, 1)

        taken += take(
            sorted(
                [article for article in remaining_columns if article["id"] not in selected_ids],
                key=lambda article: (
                    len(article.get("body") or "") < config.MIN_COLUMN_BODY_CHARS,
                    column_rank.get(article.get("source", ""), 9),
                    -score(article),
                ),
            ),
            column_quota - taken,
        )

        if taken < column_quota:
            # 칼럼이 부족하면 'pagelle/moviola/analisi' 성격의 뉴스로 채운다.
            fallback = [
                article
                for article in pool
                if content_group(article) == "news" and _is_columnish(article)
            ]
            fallback.sort(key=score, reverse=True)
            taken += take(fallback, column_quota - taken)

    news_quota = quotas.get("news", 0)
    if news_quota:
        news = [article for article in pool if content_group(article) == "news"]
        long_news = [
            article
            for article in news
            if len(article.get("body") or "") >= config.MIN_ARTICLE_BODY_CHARS
        ]
        if long_news:
            news = long_news
        # 같은 경기 보도는 하나만. 대신 다음 기사로 쿼터를 채운다.
        seen_match_keys: set[str] = set()
        unique_news = []
        for article in news:
            key = _match_key_of(article, matches)
            if key and key in seen_match_keys:
                continue
            if any(processor._similar_title(article.get("title", ""), other.get("title", "")) for other in unique_news):
                continue
            if key:
                seen_match_keys.add(key)
            unique_news.append(article)
        news = unique_news
        news.sort(
            key=lambda article: (
                not _is_match_report(article),
                -min(len(article.get("body") or ""), 12000),
                -score(article),
            )
        )
        news_taken = 0
        for team in config.FOCUS_TEAM_IDS:
            if news_taken >= news_quota:
                break
            team_news = [
                article
                for article in news
                if article["id"] not in selected_ids and team in focus_teams_of(article)
            ]
            news_taken += take(team_news, 1)
        take(
            [article for article in news if article["id"] not in selected_ids],
            news_quota - news_taken,
        )

    video_quota = quotas.get("video", 0)
    if video_quota:
        videos = [
            article
            for article in pool
            if content_group(article) == "video" and not _is_women_video(article)
        ]
        videos.sort(key=score, reverse=True)
        # 여러 팀 채널이 골고루 섞이도록 채널별로 한 개씩 먼저 고른다.
        unique_channels: dict[str, dict] = {}
        for article in videos:
            channel = article.get("video_channel") or article.get("source", "")
            unique_channels.setdefault(channel, article)
        take(list(unique_channels.values()), video_quota)
        take(videos, video_quota - len(unique_channels))

    # 칼럼/뉴스가 부족하면 포커스 팀 글에서 채워 하루 목표를 맞춘다.
    target_translated = quotas.get("news", 0) + quotas.get("column", 0)
    current_translated = sum(1 for article in selected if content_group(article) != "video")
    if current_translated < target_translated:
        remaining = [
            article
            for article in pool
            if article["id"] not in selected_ids and content_group(article) != "video"
        ]
        remaining.sort(key=score, reverse=True)
        take(remaining, target_translated - current_translated)

    log.info(
        "쿼터 선택: news=%s reddit=%s column=%s video=%s → %s개",
        quotas.get("news", 0),
        quotas.get("reddit", 0),
        quotas.get("column", 0),
        quotas.get("video", 0),
        len(selected),
    )
    return selected


def default_quotas(full_day: bool = False) -> dict[str, int]:
    if full_day:
        return dict(config.DAILY_QUOTAS)
    return dict(config.RUN_QUOTAS)


def parse_quota(value: str) -> dict[str, int]:
    quotas = {"news": 0, "column": 0, "video": 0}
    for part in value.split(","):
        key, _, raw_number = part.partition("=")
        key = key.strip()
        if key not in quotas:
            raise ValueError(f"알 수 없는 쿼터: {key}")
        quotas[key] = int(raw_number)
    return quotas


def retranslate_pending(previous: list[dict], limit: int = 12) -> dict[str, dict]:
    """API 키를 나중에 넣었을 때, 이전에 번역 대기였던 글을 조금씩 살린다."""
    if not config.OPENCODE_API_KEY or not previous:
        return {}

    pending = [
        item
        for item in previous
        if not item.get("translated") and item.get("body") and item.get("source") in ("gazzetta", "ultimouomo", "reddit")
    ][:limit]
    if not pending:
        return {}

    log.info("번역 대기 %s개 재처리", len(pending))
    llm = processor.LLM()
    cache = processor.load_cache()
    matches = processor.load_matches()
    refreshed = {}
    for article in pending:
        try:
            refreshed[article["id"]] = processor.process_article(article, llm, cache, matches)
        except Exception:
            log.exception("재번역 실패: %s", article.get("url"))
    processor.save_cache(cache)
    return refreshed


def merge(previous: list[dict], new_items: list[dict], refreshed: dict[str, dict]) -> list[dict]:
    merged = {item["id"]: item for item in previous}
    merged.update({item["id"]: item for item in new_items})
    merged.update(refreshed)

    cutoff = datetime.now(timezone.utc) - timedelta(days=config.FEED_KEEP_DAYS)
    matches = processor.load_matches()
    recent_teams = processor.recent_match_teams(matches)
    items = []
    for item in merged.values():
        published = processor.parse_dt(item.get("published"))
        if not published:
            continue
        if not item.get("history") and published < cutoff:
            continue
        # 오래된 글의 우선순위가 고정되어 '경기 직후'에 계속 남지 않도록 매번 다시 계산
        focus_teams = item.get("focus_team_ids") or item.get("team_ids") or []
        item["priority"] = processor.compute_priority(
            item["source"],
            item.get("kind", "news"),
            item.get("match"),
            published,
            focus_teams,
            matches,
        )
        item["hot"] = processor.match_is_recent(item.get("match")) or (
            0 <= (datetime.now(timezone.utc) - published).total_seconds() / 3600
            <= config.MATCH_PRIORITY_HOURS
            and bool(set(focus_teams) & recent_teams)
        )
        items.append(item)

    items, dropped = processor.dedupe_and_rank(items)
    items = items[: config.MAX_ITEMS_TOTAL]
    log.info("병합: %s개 (중복 제거 %s)", len(items), dropped)
    return items


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-fetch", action="store_true", help="data/raw.json 재사용")
    parser.add_argument("--limit", type=int, default=0, help="수집 원문을 앞에서 N개만 사용")
    parser.add_argument("--skip-fixtures", action="store_true", help="matches.json 자동 갱신 건너뛰기")
    parser.add_argument("--full-day", action="store_true", help="하루 쿼터(18/6/6/6)를 한 번에")
    parser.add_argument("--quota", help="예: news=3,reddit=1,column=1,video=6")
    parser.add_argument("--fresh", action="store_true", help="기존 articles.json 무시하고 새로 빌드")
    parser.add_argument("--retranslate", action="store_true", help="이전 번역 대기 글도 추가로 재처리")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if not args.skip_fixtures:
        try:
            fixtures.update_matches()
        except Exception:
            log.exception("경기 결과 갱신 실패 → 기존 matches.json 사용")

    if args.no_fetch:
        raw_payload = json.loads(config.RAW_FILE.read_text(encoding="utf-8"))
        raw = raw_payload.get("articles", [])
    else:
        raw = fetcher.fetch_all()

    if args.limit:
        raw = raw[: args.limit]

    previous = [] if args.fresh else load_previous()
    quotas = parse_quota(args.quota) if args.quota else default_quotas(args.full_day)
    matches = processor.load_matches()
    history_limit = config.HISTORY_PER_DAILY if args.full_day else config.HISTORY_PER_RUN
    selected = select_for_run(raw, previous, quotas, matches, history_limit)

    new_items, stats = processor.process(selected)
    attempted_ids = {article["id"] for article in selected}
    target_translated = quotas.get("news", 0) + quotas.get("column", 0)

    # 중복 제거로 쿼터가 모자라면 다음 후보를 추가로 처리한다.
    for _ in range(2):
        actual_news = sum(1 for item in new_items if content_group(item) == "news")
        actual_columns = sum(1 for item in new_items if content_group(item) == "column")
        extra_quotas = {
            "news": max(0, quotas.get("news", 0) - actual_news),
            "column": max(0, quotas.get("column", 0) - actual_columns),
            "video": 0,
        }
        if actual_news + actual_columns >= target_translated or not any(extra_quotas.values()):
            break

        extra_raw = [article for article in raw if article["id"] not in attempted_ids]
        extra_selected = select_for_run(
            extra_raw,
            previous + new_items,
            extra_quotas,
            matches,
            history_limit=0,
        )
        if not extra_selected:
            break
        attempted_ids.update(article["id"] for article in extra_selected)
        extra_items, extra_stats = processor.process(extra_selected)
        new_items = processor.dedupe_and_rank(new_items + extra_items)[0]
        for key in ("prompt_tokens", "completion_tokens", "reasoning_tokens", "cost_usd", "list_cost_usd", "allowance_usd"):
            stats["llm"][key] = round(stats["llm"].get(key, 0) + extra_stats["llm"].get(key, 0), 6)

    stats["translated"] = sum(1 for item in new_items if item.get("translated"))
    stats["original_only"] = sum(1 for item in new_items if item.get("original_only"))
    stats["selected"] = len(attempted_ids)
    stats["selected"] = len(selected)
    stats["quotas"] = quotas

    refreshed = {}
    if args.retranslate and not args.fresh:
        refreshed = retranslate_pending(previous)

    items = merge(previous, new_items, refreshed)

    total_translated = sum(1 for item in items if item.get("translated"))
    total_pending = sum(
        1 for item in items if not item.get("translated") and not item.get("original_only")
    )
    stats.update(
        {
            "merged": len(items),
            "translated_total": total_translated,
            "pending_total": total_pending,
            "video_total": sum(1 for item in items if item.get("original_only")),
        }
    )

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "stats": stats,
        "articles": items,
    }
    config.ARTICLES_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    build_site.build(items, stats)
    log.info("완료: %s", json.dumps(stats, ensure_ascii=False))


if __name__ == "__main__":
    main()

"""경기 결과 자동 갱신.

TheSportsDB 무료 test key로 최근 라운드 결과를 받아 data/matches.json 을 갱신한다.
- 기준 라운드: eventsnextleague.php (다음 경기) → 없으면 pastleague/기존 파일
- 기준 라운드 포함 최근 3개 라운드 조회
- 종료된 경기만 저장, 팀 이름은 config.TEAMS 로 매핑
- API 실패/응답 없음이면 기존 파일을 건드리지 않는다

사용법:
    python fixtures.py --dry-run
    python fixtures.py
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import time
import unicodedata
from datetime import datetime, timedelta, timezone

import requests

import config

log = logging.getLogger("fixtures")

FINISHED_STATUSES = {"FT", "AET", "PEN", "MATCH FINISHED"}
MATCH_DURATION = timedelta(hours=2)  # 대략적인 종료 시각


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = value.lower().replace("&", " and ")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _team_lookup() -> dict[str, str]:
    lookup: dict[str, str] = {}
    for team in config.TEAMS:
        for value in (team["it"], team["ko"], *team.get("aliases", [])):
            lookup[_normalize(value)] = team["id"]
    # TheSportsDB 표기
    lookup.update(
        {
            "inter milan": "inter",
            "ac milan": "milan",
            "internazionale milano": "inter",
            "ssc napoli": "napoli",
            "as roma": "roma",
            "ss lazio": "lazio",
            "acf fiorentina": "fiorentina",
            "atalanta bc": "atalanta",
            "bologna fc 1909": "bologna",
        }
    )
    return lookup


TEAM_LOOKUP = _team_lookup()


def team_id(name: str) -> str | None:
    key = _normalize(name)
    if key in TEAM_LOOKUP:
        return TEAM_LOOKUP[key]
    stripped = re.sub(r"^(ac|as|ss|ssc|us|fc|cfc|acf)\s+", "", key).strip()
    return TEAM_LOOKUP.get(stripped)


def current_season(now: datetime) -> str:
    start = now.year if now.month >= 7 else now.year - 1
    return f"{start}-{start + 1}"


def _api_get(endpoint: str, params: dict) -> dict | None:
    url = f"https://www.thesportsdb.com/api/v1/json/{config.THESPORTSDB_API_KEY}/{endpoint}"
    headers = {"User-Agent": config.USER_AGENT}
    for attempt in (1, 2):
        try:
            res = requests.get(url, params=params, headers=headers, timeout=config.HTTP_TIMEOUT)
        except requests.RequestException as exc:
            log.warning("TheSportsDB 요청 실패(%s): %s", attempt, exc)
            continue

        if res.status_code == 429 and attempt == 1:
            log.warning("TheSportsDB rate limit → 5초 대기")
            time.sleep(5)
            continue
        if res.status_code != 200:
            log.warning("TheSportsDB HTTP %s: %s", res.status_code, res.text[:200])
            return None
        try:
            return res.json()
        except ValueError:
            log.warning("TheSportsDB JSON 파싱 실패")
            return None
    return None


def _parse_dt(value: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat((value or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _to_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _anchor_round(season: str, existing: list[dict]) -> int | None:
    # 1) 다음 경기에서 라운드 확인
    payload = _api_get("eventsnextleague.php", {"id": config.THESPORTSDB_LEAGUE_ID})
    for event in (payload or {}).get("events") or []:
        if event.get("strSeason") and event.get("strSeason") != season:
            continue
        try:
            return int(event["intRound"])
        except (KeyError, TypeError, ValueError):
            continue

    # 2) 방금 끝난 경기에서 확인
    payload = _api_get("eventspastleague.php", {"id": config.THESPORTSDB_LEAGUE_ID})
    for event in (payload or {}).get("events") or []:
        try:
            return int(event["intRound"])
        except (KeyError, TypeError, ValueError):
            continue

    # 3) 기존 파일의 최대 라운드
    rounds = []
    for match in existing:
        try:
            rounds.append(int(match["round"]))
        except (KeyError, TypeError, ValueError):
            continue
    return max(rounds) if rounds else None


def _fetch_round(season: str, round_number: int) -> list[dict]:
    payload = _api_get(
        "eventsround.php",
        {"id": config.THESPORTSDB_LEAGUE_ID, "r": round_number, "s": season},
    )
    return (payload or {}).get("events") or []


def parse_events(events: list[dict], season: str, now: datetime | None = None) -> list[dict]:
    """API 이벤트 → 내부 matches 형식. 종료·팀 매핑 실패 경기는 버린다."""
    now = now or datetime.now(timezone.utc)
    matches = []

    for event in events:
        if event.get("strSeason") and event.get("strSeason") != season:
            continue
        status = (event.get("strStatus") or "").upper()
        if status and status not in FINISHED_STATUSES:
            continue

        home = team_id(event.get("strHomeTeam", ""))
        away = team_id(event.get("strAwayTeam", ""))
        if not home or not away or home == away:
            continue

        try:
            home_score = int(event["intHomeScore"])
            away_score = int(event["intAwayScore"])
        except (KeyError, TypeError, ValueError):
            continue

        kickoff = _parse_dt(event.get("strTimestamp", ""))
        if not kickoff or kickoff > now:
            continue

        try:
            round_number = int(event.get("intRound"))
        except (TypeError, ValueError):
            round_number = None

        match = {
            "home": home,
            "away": away,
            "score": f"{home_score}-{away_score}",
            "finished_at": _to_iso(kickoff + MATCH_DURATION),
            "competition": "Serie A",
            "source": "thesportsdb",
        }
        if round_number is not None:
            match["round"] = round_number
        matches.append(match)

    return matches


def _merge_key(match: dict) -> tuple[str, str, str] | None:
    finished = _parse_dt(match.get("finished_at", ""))
    if not finished or not match.get("home") or not match.get("away"):
        return None
    return (match["home"], match["away"], finished.date().isoformat())


def merge_matches(
    existing: list[dict],
    new_matches: list[dict],
    now: datetime | None = None,
    keep_days: int = config.FIXTURE_KEEP_DAYS,
) -> list[dict]:
    """API 결과를 기존 파일에 덮어쓰고, 오래된 경기를 정리한다."""
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=keep_days)
    merged: dict[tuple[str, str, str], dict] = {}

    for match in existing:
        key = _merge_key(match)
        if not key:
            continue
        finished = _parse_dt(match["finished_at"])
        if finished and finished >= cutoff:
            merged[key] = {**match, "source": match.get("source", "manual")}

    for match in new_matches:
        key = _merge_key(match)
        if not key:
            continue
        finished = _parse_dt(match["finished_at"])
        if finished and finished >= cutoff:
            merged[key] = match

    result = sorted(merged.values(), key=lambda item: item["finished_at"])
    return result[-config.FIXTURE_MAX_MATCHES :]


def update_matches(*, dry_run: bool = False, now: datetime | None = None) -> list[dict]:
    now = now or datetime.now(timezone.utc)
    existing: list[dict] = []
    if config.MATCHES_FILE.exists():
        try:
            payload = json.loads(config.MATCHES_FILE.read_text(encoding="utf-8"))
            if isinstance(payload, list):
                existing = payload
        except ValueError:
            log.warning("matches.json 파싱 실패 → 기존 파일 유지")

    season = config.FIXTURE_SEASON or current_season(now)
    anchor = _anchor_round(season, existing)
    if not anchor:
        log.warning("기준 라운드를 찾지 못했습니다. 기존 matches.json 유지")
        return existing

    rounds = sorted(
        {
            round_number
            for round_number in range(max(1, anchor - config.FIXTURE_ROUNDS_BACK), anchor + 1)
        }
    )
    log.info("fixtures: 시즌 %s / 기준 라운드 %s / 조회 %s", season, anchor, rounds)

    new_matches: list[dict] = []
    for round_number in rounds:
        events = _fetch_round(season, round_number)
        parsed = parse_events(events, season, now)
        log.info("fixtures: round %s → 종료 %s경기", round_number, len(parsed))
        new_matches.extend(parsed)

    if not new_matches:
        log.warning("fixtures: 새 결과 없음 → 기존 matches.json 유지")
        return existing

    merged = merge_matches(existing, new_matches, now)
    if dry_run:
        print(json.dumps(merged, ensure_ascii=False, indent=2))
        log.info("fixtures(dry-run): %s경기", len(merged))
        return merged

    config.MATCHES_FILE.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    log.info("fixtures: matches.json %s경기 저장", len(merged))
    return merged


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="파일을 쓰지 않고 출력")
    parser.add_argument("--season", help="예: 2026-2027")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if args.season:
        config.FIXTURE_SEASON = args.season
    update_matches(dry_run=args.dry_run)


if __name__ == "__main__":
    main()

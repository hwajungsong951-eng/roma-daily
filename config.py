"""세리에A 데일리 - 공통 설정.

여기 값만 고치면 소스/팀/영상 채널을 바꿀 수 있게 최대한 단순하게 유지한다.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
SITE_DIR = ROOT / "site"
TEMPLATE_DIR = ROOT / "templates"

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:  # dotenv 없이도 동작
    pass

DATA_DIR.mkdir(exist_ok=True)
SITE_DIR.mkdir(exist_ok=True)

TIMEZONE = "Asia/Seoul"

# 봇이라는 걸 밝히고, 과한 요청을 피한다.
USER_AGENT = os.getenv(
    "FEED_USER_AGENT",
    "seriea-feed/0.1 (personal non-profit fan translation; contact: you@example.com)",
)
HTTP_TIMEOUT = 25
REQUEST_DELAY = 0.8  # 같은 사이트 연속 요청 사이 대기(초)

# --- 수집 범위 -------------------------------------------------------------
MAX_AGE_HOURS = 72          # 이보다 오래된 기사는 새로 수집하지 않음 (주 2~3회 발행 매체 고려)
FEED_KEEP_DAYS = 7          # 사이트에 남겨두는 기사 보관 기간
MAX_ITEMS_PER_SOURCE = 12
MAX_ITEMS_TOTAL = 250
MATCH_PRIORITY_HOURS = 24   # 경기 종료 후 이 시간 안의 기사는 '경기 직후' 우선 노출

GAZZETTA_FEEDS = [
    "https://www.gazzetta.it/rss/serie-a.xml",
    "https://www.gazzetta.it/rss/calcio.xml",
]

# RSS 기반 이탈리아 매체. Gazzetta 피드가 죽어 있어도 나머지가 사이트를 채운다.
# url_include: 기사 URL에 이 조각이 하나라도 있어야 수집 (빈 리스트 = 전부)
RSS_SOURCES = [
    {
        "key": "gazzetta",
        "feeds": GAZZETTA_FEEDS,
        "max_items": 6,
        "page_budget": 4,
        "url_include": ["/roma/"],
    },
    {
        "key": "corrieredellosport",
        "feeds": ["https://www.corrieredellosport.it/rss/calcio"],
        "max_items": 10,
        "page_budget": 10,
        "url_include": ["/roma/"],
    },
    {
        "key": "tuttosport",
        "feeds": ["https://www.tuttosport.com/rss/calcio"],
        "max_items": 10,
        "page_budget": 10,
        "url_include": ["/roma/"],
    },
    {
        "key": "forzaroma",
        "feeds": ["https://www.forzaroma.info/feed/"],
        "max_items": 12,
        "page_budget": 0,
        "url_include": [],
        "full_content": True,
        "lang": "it",
    },
    {
        "key": "romanews",
        "feeds": ["https://www.romanews.eu/feed/"],
        "max_items": 8,
        "page_budget": 6,
        "url_include": [],
        "lang": "it",
    },
    {
        "key": "sportellate",
        "feeds": [
            "https://www.sportellate.it/feed/",
            "https://www.sportellate.it/tag/roma/feed/",
        ],
        "max_items": 20,
        "page_budget": 0,
        "url_include": [],
        "full_content": True,
        "max_age_hours": 24 * 365 * 3,
        "lang": "it",
    },
    {
        "key": "sportellate_history",
        "feeds": ["https://www.sportellate.it/tag/storia/feed/"],
        "max_items": 6,
        "page_budget": 0,
        "url_include": [],
        "full_content": True,
        "max_age_hours": 24 * 365 * 3,
        "history": True,
        "lang": "it",
    },
    {
        "key": "footballitalia",
        "feeds": ["https://football-italia.net/feed/"],
        "max_items": 6,
        "page_budget": 0,
        "url_include": [],
        "title_include": ["roma"],
        "full_content": True,
        "lang": "en",
    },
    {
        "key": "footballzone",
        "feeds": ["https://www.football-zone.net/feed/"],
        "max_items": 4,
        "page_budget": 4,
        "url_include": [],
        "title_include": ["ローマ"],
        "lang": "ja",
    },
    {
        "key": "footballchannel",
        "feeds": ["https://www.footballchannel.jp/feed/"],
        "max_items": 4,
        "page_budget": 4,
        "url_include": [],
        "title_include": ["ローマ"],
        "lang": "ja",
    },
    {
        "key": "romapress",
        "feeds": ["https://romapress.net/feed/"],
        "max_items": 10,
        "page_budget": 0,
        "url_include": [],
        "full_content": True,
        "lang": "en",
    },
    {
        "key": "chiesaditotti",
        "feeds": ["https://www.chiesaditotti.com/rss/index.xml"],
        "max_items": 8,
        "page_budget": 0,
        "url_include": [],
        "full_content": True,
        "lang": "en",
    },
    {
        "key": "ilmessaggero",
        "feeds": ["https://www.ilmessaggero.it/rss/sport.xml"],
        "max_items": 8,
        "page_budget": 6,
        "url_include": [],
        "lang": "it",
    },
    {
        "key": "guardian",
        "feeds": ["https://www.theguardian.com/football/rss"],
        "max_items": 6,
        "page_budget": 4,
        "url_include": [],
        "lang": "en",
    },
    {
        "key": "cbssports",
        "feeds": ["https://www.cbssports.com/rss/headlines/soccer/"],
        "max_items": 6,
        "page_budget": 4,
        "url_include": [],
        "lang": "en",
    },
    {
        "key": "asroma_blog",
        "feeds": ["https://asromadenshihokoku.blogspot.com/feeds/posts/default?alt=rss"],
        "max_items": 8,
        "page_budget": 0,
        "url_include": [],
        "full_content": True,
        "lang": "ja",
    },
    {
        "key": "gentlemanultra",
        "feeds": ["https://www.gentlemanultra.com/feed/"],
        "max_items": 6,
        "page_budget": 0,
        "url_include": [],
        "full_content": True,
        "max_age_hours": 24 * 30,
        "history": True,
        "lang": "en",
    },
]
REDDIT_SUBREDDIT = "seriea"
REDDIT_TOP_COMMENTS = 0
REDDIT_MAX_POSTS = 12
REDDIT_REQUEST_DELAY = 0.7
REDDIT_MIN_BODY_CHARS = 700
# Reddit은 설명 있는 고유 UA를 요구한다. /u/닉네임을 넣어두면 좋다.
REDDIT_USER_AGENT = os.getenv(
    "REDDIT_USER_AGENT",
    "seriea-feed/0.2 (personal non-profit Serie A fan feed)",
)
REDDIT_SKIP_TITLES = (
    "r/SerieA Scoreboard",
    "Match Thread",
    "Daily Discussion",
    "Weekly Discussion",
)
YOUTUBE_MAX_PER_CHANNEL = 6
YOUTUBE_MAX_ITEMS = 24
YOUTUBE_MAX_AGE_HOURS = 72

# --- 경기 결과 자동 갱신 (TheSportsDB) -------------------------------------
# 무료 test key 123. 운영 시 본인 키로 바꾸는 걸 권장.
THESPORTSDB_LEAGUE_ID = "4332"  # Italian Serie A
THESPORTSDB_API_KEY = os.getenv("THESPORTSDB_API_KEY", "123")
FIXTURE_SEASON = os.getenv("FIXTURE_SEASON", "")  # 비우면 현재 날짜로 자동 계산
FIXTURE_ROUNDS_BACK = 2    # 기준 라운드 포함 최근 3개 라운드 조회
FIXTURE_KEEP_DAYS = 14
FIXTURE_MAX_MATCHES = 60

# 칼럼은 아주 긴 장문이 있어 번역 비용을 통제한다.
MAX_COLUMN_BODY_CHARS = 12000
MAX_HISTORY_BODY_CHARS = 12000

# 한 번 번역해두고 역사 섹션에 계속 보여줄 큐레이션. 새 글을 추가하면 다음 실행에서 번역된다.
HISTORY_SEEDS = [
    {
        "url": "https://www.themagicsq.com/seasons/as-roma-historic-1982-83-scudetto-serie-a.htm",
        "title": "AS Roma's Historic 1982-83 Scudetto",
        "published": "2023-05-08",
    },
    {
        "url": "https://en.wikipedia.org/wiki/History_of_AS_Roma",
        "title": "History of AS Roma",
        "published": "2024-01-01",
    },
]

# --- 소스 메타 -------------------------------------------------------------
SOURCES = {
    "gazzetta": {"label": "Gazzetta", "color": "#e4002b", "weight": 8, "group": "news"},
    "corrieredellosport": {"label": "Corriere dello Sport", "color": "#0a5ca8", "weight": 9, "group": "news"},
    "tuttosport": {"label": "Tuttosport", "color": "#c8102e", "weight": 9, "group": "news"},
    "forzaroma": {"label": "ForzaRoma", "color": "#8e1f2f", "weight": 9, "group": "team"},
    "romanews": {"label": "Romanews", "color": "#b3272d", "weight": 8, "group": "team"},
    "ultimouomo": {"label": "Ultimo Uomo", "color": "#1f6feb", "weight": 8, "group": "column"},
    "sportellate": {"label": "Sportellate", "color": "#f97316", "weight": 8, "group": "column"},
    "sportellate_history": {"label": "Sportellate · 역사", "color": "#c2410c", "weight": 8, "group": "column"},
    "footballitalia": {"label": "Football Italia", "color": "#1a4d8f", "weight": 7, "group": "team"},
    "footballzone": {"label": "フットボールゾーン", "color": "#0f766e", "weight": 7, "group": "column"},
    "footballchannel": {"label": "フットボールチャンネル", "color": "#0d9488", "weight": 7, "group": "column"},
    "asroma_blog": {"label": "AS ROMA電子報告", "color": "#8e1f2f", "weight": 7, "group": "team"},
    "gentlemanultra": {"label": "The Gentleman Ultra", "color": "#7c3aed", "weight": 7, "group": "column"},
    "romapress": {"label": "RomaPress", "color": "#8e1f2f", "weight": 8, "group": "team"},
    "chiesaditotti": {"label": "Chiesa di Totti", "color": "#991b1b", "weight": 8, "group": "team"},
    "ilmessaggero": {"label": "Il Messaggero", "color": "#7a1f2b", "weight": 7, "group": "team"},
    "guardian": {"label": "The Guardian", "color": "#052962", "weight": 8, "group": "team"},
    "cbssports": {"label": "CBS Sports", "color": "#1d4ed8", "weight": 7, "group": "team"},
    "history": {"label": "역사 아카이브", "color": "#b45309", "weight": 8, "group": "column"},
    "reddit": {"label": "r/seriea", "color": "#ff4500", "weight": 6, "group": "column"},
    "youtube": {"label": "YouTube", "color": "#ff0000", "weight": 4, "group": "video"},
}

SOURCE_GROUPS = {key: meta["group"] for key, meta in SOURCES.items()}

# 사이트에서 다루는 팀. 나머지 팀은 상대팀 이름 표시·경기 매칭용으로만 사용한다.
FOCUS_TEAM_IDS = ["roma"]
FOCUS_SOURCES = {
    "forzaroma",
    "romanews",
    "asroma_blog",
    "romapress",
    "chiesaditotti",
    "history",
}

# 하루 목표: 기사 3 + 칼럼 4 = 번역 7개, 영상 4개 원본 (오전 1회)
DAILY_QUOTAS = {"news": 3, "column": 4, "video": 4}
RUN_QUOTAS = {"news": 3, "column": 4, "video": 4}
HISTORY_PER_DAILY = 1
HISTORY_PER_RUN = 1
RUNS_PER_DAY = 1

# 장문 기사/칼럼을 우선한다.
MIN_ARTICLE_BODY_CHARS = 1200
MIN_COLUMN_BODY_CHARS = 600

TAG_ORDER = ["경기", "칼럼", "팬 칼럼", "역사", "인터뷰", "이적", "전술", "부상", "팬 반응", "영상"]

FAN_SOURCES = {"chiesaditotti", "forzaroma", "romanews", "asroma_blog"}

HISTORY_HINTS = (
    "storico",
    "storica",
    "scudetto",
    "ricordo",
    "leggenda",
    "mito",
    "epoca",
    "anni fa",
    "history",
    "historical",
    "legend",
    "remember",
    "years ago",
    "歴史",
    "伝説",
    "あの頃",
    "過去",
)


def is_history_text(text: str) -> bool:
    value = (text or "").lower()
    return any(hint in value for hint in HISTORY_HINTS)

# --- 팀 -------------------------------------------------------------------
# 2026-27 세리에A 20개 팀. 승격/강등이 바뀌면 이 목록만 수정하면 된다.
TEAMS = [
    {"id": "atalanta", "it": "Atalanta", "ko": "아탈란타", "color": "#1e71b8", "aliases": ["atalanta", "orobici"]},
    {"id": "bologna", "it": "Bologna", "ko": "볼로냐", "color": "#a21c26", "aliases": ["bologna", "felsinei"]},
    {"id": "cagliari", "it": "Cagliari", "ko": "칼리아리", "color": "#b3272d", "aliases": ["cagliari"]},
    {"id": "como", "it": "Como", "ko": "코모", "color": "#1b3a6b", "aliases": ["como"]},
    {"id": "fiorentina", "it": "Fiorentina", "ko": "피오렌티나", "color": "#6a2c91", "aliases": ["fiorentina", "viola"]},
    {"id": "frosinone", "it": "Frosinone", "ko": "프로시노네", "color": "#f5c500", "aliases": ["frosinone", "ciociari"]},
    {"id": "genoa", "it": "Genoa", "ko": "제노아", "color": "#b3202a", "aliases": ["genoa", "grifone"]},
    {"id": "inter", "it": "Inter", "ko": "인테르", "color": "#0b1f4b", "aliases": ["inter", "internazionale"]},
    {"id": "juventus", "it": "Juventus", "ko": "유벤투스", "color": "#111111", "aliases": ["juventus", "juve"]},
    {"id": "lazio", "it": "Lazio", "ko": "라치오", "color": "#87d8f7", "aliases": ["lazio"]},
    {"id": "lecce", "it": "Lecce", "ko": "레체", "color": "#f2c500", "aliases": ["lecce", "salentini"]},
    {"id": "milan", "it": "Milan", "ko": "밀란", "color": "#c8102e", "aliases": ["milan", "ac milan"]},
    {"id": "monza", "it": "Monza", "ko": "몬차", "color": "#e30613", "aliases": ["monza", "brianzoli"]},
    {"id": "napoli", "it": "Napoli", "ko": "나폴리", "color": "#12a0d7", "aliases": ["napoli", "partenopei"]},
    {"id": "parma", "it": "Parma", "ko": "파르마", "color": "#f5c518", "aliases": ["parma", "crociati", "パルマ"]},
    {"id": "roma", "it": "Roma", "ko": "로마", "color": "#8e1f2f", "aliases": ["roma", "as roma", "ローマ", "lupi"]},
    {"id": "sassuolo", "it": "Sassuolo", "ko": "사수올로", "color": "#00a752", "aliases": ["sassuolo", "neroverdi"]},
    {"id": "torino", "it": "Torino", "ko": "토리노", "color": "#7a1f2b", "aliases": ["torino"]},
    {"id": "udinese", "it": "Udinese", "ko": "우디네세", "color": "#111111", "aliases": ["udinese", "zebrette"]},
    {"id": "venezia", "it": "Venezia", "ko": "베네치아", "color": "#f26b21", "aliases": ["venezia", "lagunari"]},
]

# 팀별 공식 YouTube 핸들. 채널이 없거나 핸들이 바뀌면 자동으로 건너뛴다.
# 채널 ID는 data/youtube_channels.json 에 캐시된다.
YOUTUBE_CHANNELS = [
    {"team": "seriea", "handle": "SerieA", "label": "Serie A"},
    {"team": "roma", "handle": "ASRoma", "label": "AS Roma"},
]

# --- LLM (OpenCode Go / Console) ------------------------------------------
# Go 구독이면 기본값 그대로 OPENCODE_API_KEY 만 넣으면 된다.
# Console(종량제)을 쓰려면 OPENCODE_BASE_URL 을
#   https://opencode.ai/inference/openai/v1
# 로 바꾸고 OPENCODE_MODEL 을 Console 모델 ID로 지정.
OPENCODE_BASE_URL = os.getenv(
    "OPENCODE_BASE_URL", "https://opencode.ai/inference/go/openai/v1"
).rstrip("/")
OPENCODE_MODEL = os.getenv("OPENCODE_MODEL", "deepseek-v4.1-flash").strip()
OPENCODE_REASONING_EFFORT = os.getenv("OPENCODE_REASONING_EFFORT", "none").strip()
OPENCODE_SESSION = os.getenv("OPENCODE_SESSION", "seriea-feed").strip()


def _clean_secret(value: str | None) -> str:
    """붙여넣기 실수(공백·따옴표·변수명 포함)를 정리한다."""
    if not value:
        return ""
    value = value.strip().strip('"').strip("'").strip()
    if value.startswith("OPENCODE_API_KEY="):
        value = value.split("=", 1)[1].strip().strip('"').strip("'").strip()
    return value


OPENCODE_API_KEY = _clean_secret(os.getenv("OPENCODE_API_KEY") or os.getenv("OPENCODE_KEY"))

# 번역 캐시/프롬프트가 바뀌면 올려서 전체 재번역을 유도한다.
PROMPT_VERSION = "v1"

RAW_FILE = DATA_DIR / "raw.json"
ARTICLES_FILE = DATA_DIR / "articles.json"
CACHE_FILE = DATA_DIR / "cache.json"
MATCHES_FILE = DATA_DIR / "matches.json"
YOUTUBE_CACHE_FILE = DATA_DIR / "youtube_channels.json"


def team_by_id(team_id: str) -> dict | None:
    for team in TEAMS:
        if team["id"] == team_id:
            return team
    return None

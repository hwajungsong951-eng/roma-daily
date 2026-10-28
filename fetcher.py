"""원문 수집기.

소스
- Gazzetta dello Sport RSS (세리에A/칼초)
- r/seriea (RSS, 선택적으로 Reddit OAuth로 인기 댓글)
- Ultimo Uomo RSS (전문은 content:encoded에 들어있음)
- 팀별 YouTube 채널 RSS (config.YOUTUBE_CHANNELS)

수집 결과는 data/raw.json 에 저장한다. 번역은 processor.py 담당.
"""
from __future__ import annotations

import hashlib
import html
import json
import logging
import os
import re
import time
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import feedparser
import requests
from bs4 import BeautifulSoup

import config

log = logging.getLogger("fetcher")

_session = requests.Session()
_session.headers.update(
    {
        "User-Agent": config.USER_AGENT,
        "Accept-Language": "it-IT,it;q=0.9,en;q=0.7",
    }
)


# --- 공통 유틸 -------------------------------------------------------------
def http_get(url: str, *, tries: int = 3, **kwargs) -> requests.Response | None:
    for attempt in range(1, tries + 1):
        try:
            res = _session.get(url, timeout=config.HTTP_TIMEOUT, **kwargs)
            if res.status_code == 200:
                return res
            if res.status_code in (403, 429):
                log.warning("HTTP %s (차단/제한) %s", res.status_code, url)
                return None
            log.warning("HTTP %s %s", res.status_code, url)
        except requests.RequestException as exc:
            log.warning("요청 실패(%s/%s) %s: %s", attempt, tries, url, exc)
            time.sleep(1.5 * attempt)
    return None


def make_id(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]


def to_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def entry_datetime(entry) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        parsed = entry.get(key)
        if parsed:
            return datetime(*parsed[:6], tzinfo=timezone.utc)
    for key in ("published", "updated"):
        raw = entry.get(key)
        if raw:
            try:
                dt = parsedate_to_datetime(raw)
                return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
            except (TypeError, ValueError):
                pass
    return None


def is_fresh(dt: datetime | None, hours: int = config.MAX_AGE_HOURS) -> bool:
    return bool(dt) and dt >= datetime.now(timezone.utc) - timedelta(hours=hours)


def clean_text(value: str) -> str:
    if not value:
        return ""
    soup = BeautifulSoup(html.unescape(value), "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    for br in soup.find_all("br"):
        br.replace_with("\n")
    text = soup.get_text("\n")
    lines = []
    for line in text.splitlines():
        line = re.sub(r"\s+", " ", line).strip()
        if line:
            lines.append(line)
    return "\n".join(lines)


def first_image(value: str) -> str | None:
    if not value:
        return None
    soup = BeautifulSoup(html.unescape(value), "html.parser")
    img = soup.find("img")
    if img and img.get("src"):
        return img["src"]
    m = re.search(r'<img[^>]+src=["\']([^"\']+)', value)
    return m.group(1) if m else None


def rss_image(entry) -> str | None:
    for key in ("media_thumbnail", "media_content"):
        media = entry.get(key) or []
        for item in media:
            if item.get("url"):
                return item["url"]
    for enclosure in entry.get("enclosures") or []:
        if str(enclosure.get("type", "")).startswith("image") and enclosure.get("href"):
            return enclosure["href"]
    return first_image(entry.get("summary", "") or (entry.get("content") or [{}])[0].get("value", ""))


def article_body_from_html(page: str) -> str:
    """기사 페이지에서 본문 후보를 뽑아 가장 긴 쪽을 쓴다."""
    soup = BeautifulSoup(page, "html.parser")

    # 1) JSON-LD articleBody (가장 깔끔한 경우가 많음)
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except (TypeError, ValueError):
            continue
        nodes = data if isinstance(data, list) else [data]
        for node in nodes:
            if isinstance(node, dict) and isinstance(node.get("articleBody"), str):
                text = clean_text(node["articleBody"])
                if len(text) > 400:
                    return text

    # 2) 흔한 본문 컨테이너
    selectors = [
        "article p",
        "[data-element='paragraph']",
        ".article-body p",
        ".article__body p",
        ".content p",
        "main p",
    ]
    best = ""
    for selector in selectors:
        paragraphs = []
        for node in soup.select(selector):
            text = node.get_text(" ", strip=True)
            if len(text) >= 30 and not re.search(r"(cookie|abbonat|newsletter)", text, re.I):
                paragraphs.append(text)
        candidate = "\n\n".join(paragraphs)
        if len(candidate) > len(best):
            best = candidate
    return best


def extract_page_body(url: str) -> str:
    res = http_get(url)
    if not res or "html" not in (res.headers.get("content-type") or ""):
        return ""
    return article_body_from_html(res.text)


def base_article(
    *,
    source: str,
    title: str,
    url: str,
    published: datetime | None,
    body: str,
    excerpt: str = "",
    author: str = "",
    image: str | None = None,
    lang: str = "it",
    kind: str = "news",
    comments: list | None = None,
    categories: list[str] | None = None,
) -> dict:
    meta = config.SOURCES[source]
    published = published or datetime.now(timezone.utc)
    body = (body or "").strip()
    excerpt = (excerpt or body[:240]).strip()
    return {
        "id": make_id(url),
        "source": source,
        "source_label": meta["label"],
        "kind": kind,
        "title": clean_text(title),
        "url": url,
        "published": to_iso(published),
        "author": clean_text(author),
        "lang": lang,
        "excerpt": excerpt[:400],
        "body": body,
        "image": image,
        "comments": comments or [],
        "categories": categories or [],
    }


# --- RSS 기반 이탈리아 매체 (Gazzetta / Corriere dello Sport / Tuttosport) ---
def fetch_rss_source(spec: dict) -> list[dict]:
    key = spec["key"]
    label = config.SOURCES[key]["label"]
    seen: dict[str, dict] = {}
    page_budget = spec.get("page_budget", 6)
    include = spec.get("url_include") or []
    title_include = spec.get("title_include") or []
    category_include = spec.get("category_include") or []
    full_content = spec.get("full_content", False)

    for feed_url in spec["feeds"]:
        res = http_get(feed_url)
        if not res:
            continue
        feed = feedparser.parse(res.content)
        log.info("%s feed %s: %s개", label, feed_url, len(feed.entries))

        for entry in feed.entries:
            url = (entry.get("link") or "").split("?intcmp=")[0].strip()
            if not url or url in seen:
                continue
            if include and not any(fragment in url for fragment in include):
                continue
            categories = [tag.get("term", "") for tag in entry.get("tags") or []]
            if category_include:
                category_text = " ".join(categories).lower()
                if not any(category.lower() in category_text for category in category_include):
                    continue

            published = entry_datetime(entry)
            if not is_fresh(published, spec.get("max_age_hours", config.MAX_AGE_HOURS)):
                continue

            title = entry.get("title", "")
            summary = clean_text(entry.get("summary", ""))
            if title_include and not any(
                keyword in f"{title} {summary}".lower() for keyword in title_include
            ):
                continue

            content = ""
            if entry.get("content"):
                content = clean_text(entry["content"][0].get("value", ""))

            body = content or summary
            # RSS 요약이 짧으면 원문 페이지에서 본문을 보강한다.
            if len(body) < 1200 and page_budget > 0:
                page_budget -= 1
                time.sleep(config.REQUEST_DELAY)
                page_body = extract_page_body(url)
                if len(page_body) > len(body):
                    body = page_body

            if full_content and len(body) < 300:
                continue

            excerpt = summary
            if len(excerpt) < 120 and len(body) > len(excerpt):
                excerpt = body[:240]

            article = base_article(
                source=key,
                title=title,
                url=url,
                published=published,
                body=body,
                excerpt=excerpt,
                author=entry.get("author", ""),
                image=rss_image(entry),
                lang=spec.get("lang", "it"),
                categories=categories,
            )
            if spec.get("history"):
                article["history_hint"] = True
            seen[url] = article

    articles = list(seen.values())[: spec.get("max_items", config.MAX_ITEMS_PER_SOURCE)]
    log.info("%s %s개 수집", label, len(articles))
    return articles


def fetch_rss_sources() -> list[dict]:
    articles: list[dict] = []
    for spec in config.RSS_SOURCES:
        articles.extend(fetch_rss_source(spec))
    return articles


# --- Ultimo Uomo ----------------------------------------------------------
def fetch_ultimouomo() -> list[dict]:
    res = http_get("https://www.ultimouomo.com/feed/")
    if not res:
        return []
    feed = feedparser.parse(res.content)
    articles = []

    for entry in feed.entries:
        published = entry_datetime(entry)
        if not is_fresh(published):
            continue

        category = " ".join(tag.get("term", "") for tag in entry.get("tags") or [])
        if category and "calcio" not in category.lower():
            continue

        raw_html = entry.content[0].get("value", "") if entry.get("content") else ""
        body = clean_text(raw_html)
        summary = clean_text(entry.get("summary", ""))
        if len(body) < 300:
            continue

        articles.append(
            base_article(
                source="ultimouomo",
                title=entry.get("title", ""),
                url=entry.get("link", ""),
                published=published,
                body=body,
                excerpt=summary,
                author=entry.get("author", ""),
                image=rss_image(entry),
                lang="it",
            )
        )

    articles = articles[: config.MAX_ITEMS_PER_SOURCE]
    log.info("Ultimo Uomo %s개 수집", len(articles))
    return articles


# --- Reddit ---------------------------------------------------------------
def _reddit_credentials() -> tuple[str, str] | None:
    client_id = (os.getenv("REDDIT_CLIENT_ID") or "").strip()
    client_secret = (os.getenv("REDDIT_CLIENT_SECRET") or "").strip()
    if not client_id or not client_secret:
        return None
    return client_id, client_secret


def _reddit_oauth_token() -> str | None:
    credentials = _reddit_credentials()
    if not credentials:
        log.info("Reddit OAuth 자격증명 없음 → 공개 RSS 모드")
        return None

    client_id, client_secret = credentials
    try:
        res = requests.post(
            "https://www.reddit.com/api/v1/access_token",
            auth=(client_id, client_secret),
            data={"grant_type": "client_credentials"},
            headers={"User-Agent": config.REDDIT_USER_AGENT},
            timeout=config.HTTP_TIMEOUT,
        )
    except requests.RequestException as exc:
        log.warning("Reddit OAuth 요청 실패: %s", exc)
        return None

    if res.status_code in (401, 403):
        log.warning(
            "Reddit OAuth 인증 실패(%s): REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET을 확인하세요",
            res.status_code,
        )
        return None
    if res.status_code != 200:
        log.warning("Reddit OAuth HTTP %s: %s", res.status_code, res.text[:200])
        return None

    try:
        token = res.json().get("access_token")
    except ValueError:
        log.warning("Reddit OAuth 응답이 JSON이 아닙니다")
        return None

    if token:
        log.info("Reddit OAuth 토큰 발급 완료")
    else:
        log.warning("Reddit OAuth 토큰이 비어 있습니다")
    return token


def _reddit_get(token: str, path: str, params: dict | None = None):
    """oauth.reddit.com GET. 429는 한 번만 짧게 기다린다."""
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": config.REDDIT_USER_AGENT,
    }
    query = {**(params or {}), "raw_json": 1}
    for attempt in (1, 2):
        try:
            res = requests.get(
                "https://oauth.reddit.com" + path,
                params=query,
                headers=headers,
                timeout=config.HTTP_TIMEOUT,
            )
        except requests.RequestException as exc:
            log.warning("Reddit 요청 실패 %s: %s", path, exc)
            return None

        if res.status_code == 429 and attempt == 1:
            wait = 5.0
            try:
                wait = min(float(res.headers.get("X-Ratelimit-Reset", "")), 10.0)
            except (TypeError, ValueError):
                pass
            log.warning("Reddit rate limit → %.0f초 대기", wait)
            time.sleep(max(1.0, wait))
            continue
        if res.status_code == 401:
            log.warning("Reddit 토큰 만료/거부: %s", path)
            return None
        if res.status_code >= 400:
            log.warning("Reddit HTTP %s: %s", res.status_code, path)
            return None

        try:
            return res.json()
        except ValueError:
            log.warning("Reddit JSON 파싱 실패: %s", path)
            return None
    return None


def _reddit_hot_posts(payload) -> list[dict]:
    if not isinstance(payload, dict):
        return []
    children = payload.get("data", {}).get("children", [])
    posts = []
    for child in children:
        data = child.get("data", {})
        if child.get("kind") != "t3" or not data:
            continue
        if data.get("stickied") or data.get("over_18"):
            continue
        published = datetime.fromtimestamp(data.get("created_utc", 0), tz=timezone.utc)
        if not is_fresh(published):
            continue
        title = data.get("title", "")
        if any(skip.lower() in title.lower() for skip in config.REDDIT_SKIP_TITLES):
            continue
        if len((data.get("selftext") or "").strip()) < config.REDDIT_MIN_BODY_CHARS:
            continue
        posts.append(data)
    return posts


def _reddit_comments(permalink: str, token: str, limit: int) -> list[dict]:
    payload = _reddit_get(
        token,
        permalink.rstrip("/") + ".json",
        {"sort": "top", "limit": limit, "depth": 1},
    )
    if not isinstance(payload, list) or len(payload) < 2:
        return []

    comments = []
    for child in payload[1].get("data", {}).get("children", []):
        data = child.get("data", {})
        if child.get("kind") != "t1" or not data:
            continue
        if data.get("stickied"):
            continue
        body = (data.get("body") or "").strip()
        author = data.get("author") or ""
        if not body or body in ("[deleted]", "[removed]") or author == "[deleted]":
            continue
        comments.append(
            {
                "author": author,
                "score": int(data.get("score") or 0),
                "body": body,
            }
        )

    comments.sort(key=lambda item: item["score"], reverse=True)
    return comments[:limit]


def _reddit_image(data: dict) -> str | None:
    preview = data.get("preview", {}).get("images") or []
    if preview:
        source = preview[0].get("source", {})
        if source.get("url"):
            return source["url"]
    thumbnail = data.get("thumbnail")
    if thumbnail and str(thumbnail).startswith("http"):
        return thumbnail
    return None


def _fetch_reddit_oauth(token: str) -> list[dict]:
    payload = _reddit_get(
        token,
        f"/r/{config.REDDIT_SUBREDDIT}/hot",
        {"limit": 30},
    )
    candidates = _reddit_hot_posts(payload)
    if not candidates:
        log.warning("Reddit OAuth 글 목록이 비었습니다")
        return []

    posts: list[dict] = []
    for data in candidates[: config.REDDIT_MAX_POSTS]:
        permalink = data.get("permalink") or ""
        title = data.get("title", "")
        comments = []
        if config.REDDIT_TOP_COMMENTS > 0 and permalink and (data.get("num_comments") or 0) > 0:
            comments = _reddit_comments(permalink, token, config.REDDIT_TOP_COMMENTS)
            time.sleep(config.REDDIT_REQUEST_DELAY)

        body = (data.get("selftext") or "").strip()
        if body in ("[deleted]", "[removed]"):
            body = ""

        posts.append(
            base_article(
                source="reddit",
                title=title,
                url="https://www.reddit.com" + permalink if permalink else data.get("url", ""),
                published=datetime.fromtimestamp(data.get("created_utc", 0), tz=timezone.utc),
                body=body,
                excerpt=body[:240],
                author=data.get("author", ""),
                image=_reddit_image(data),
                lang="en",
                kind="reddit",
                comments=comments,
            )
        )

    log.info(
        "Reddit OAuth: 글 %s개 / 긴 글 %s개",
        len(posts),
        sum(1 for post in posts if len(post["body"]) >= config.REDDIT_MIN_BODY_CHARS),
    )
    return posts


def _fetch_reddit_rss() -> list[dict]:
    res = http_get(f"https://www.reddit.com/r/{config.REDDIT_SUBREDDIT}/.rss")
    if not res:
        return []
    feed = feedparser.parse(res.content)
    posts = []
    for entry in feed.entries:
        published = entry_datetime(entry)
        if not is_fresh(published):
            continue
        title = entry.get("title", "")
        if any(skip.lower() in title.lower() for skip in config.REDDIT_SKIP_TITLES):
            continue
        raw_html = entry.content[0].get("value", "") if entry.get("content") else ""
        raw_html = re.split(r"submitted by", raw_html, flags=re.I)[0]
        body = clean_text(raw_html)
        if "content not supported on old Reddit" in body:
            body = ""
        if len(body) < config.REDDIT_MIN_BODY_CHARS:
            continue
        posts.append(
            base_article(
                source="reddit",
                title=title,
                url=entry.get("link", ""),
                published=published,
                body=body,
                excerpt=body[:240],
                author=entry.get("author", "").replace("/u/", ""),
                image=rss_image(entry),
                lang="en",
                kind="reddit",
            )
        )
    return posts


def fetch_reddit() -> list[dict]:
    token = _reddit_oauth_token()
    posts = _fetch_reddit_oauth(token) if token else []

    if not posts:
        # 자격증명이 없거나 API가 실패하면 공개 RSS로 대체한다. (댓글은 가져오지 않음)
        posts = _fetch_reddit_rss()
        mode = "RSS only"
    else:
        mode = "OAuth + long-form posts"

    posts = posts[: config.REDDIT_MAX_POSTS]
    log.info("Reddit %s개 수집 (%s)", len(posts), mode)
    return posts


# --- 역사 아카이브 -------------------------------------------------------
def fetch_history_seeds() -> list[dict]:
    articles: list[dict] = []
    for seed in config.HISTORY_SEEDS:
        res = http_get(seed["url"])
        if not res:
            log.warning("역사 페이지 실패: %s", seed["url"])
            continue
        body = article_body_from_html(res.text)[: config.MAX_HISTORY_BODY_CHARS]
        if len(body) < 500:
            log.warning("역사 본문 추출 실패: %s", seed["url"])
            continue

        try:
            published = datetime.fromisoformat(seed.get("published", "")).replace(
                hour=12, tzinfo=timezone.utc
            )
        except ValueError:
            published = datetime.now(timezone.utc)

        image = None
        soup = BeautifulSoup(res.text, "html.parser")
        og_image = soup.find("meta", property="og:image")
        if og_image and og_image.get("content"):
            image = og_image["content"]

        article = base_article(
            source="history",
            title=seed["title"],
            url=seed["url"],
            published=published,
            body=body,
            excerpt=body[:240],
            author="History archive",
            image=image,
            lang="en",
        )
        article["history_hint"] = True
        articles.append(article)
        time.sleep(config.REQUEST_DELAY)

    log.info("역사 아카이브 %s개 수집", len(articles))
    return articles


# --- YouTube --------------------------------------------------------------
def _load_channel_cache() -> dict:
    if config.YOUTUBE_CACHE_FILE.exists():
        try:
            return json.loads(config.YOUTUBE_CACHE_FILE.read_text(encoding="utf-8"))
        except ValueError:
            pass
    return {}


def _resolve_channel_id(handle: str) -> str | None:
    res = http_get(f"https://www.youtube.com/@{handle}", headers={"Cookie": "CONSENT=YES+1"})
    if not res:
        return None
    for pattern in (
        r'"externalId":"(UC[\w-]{22})"',
        r'"channelId":"(UC[\w-]{22})"',
        r'"browseId":"(UC[\w-]{22})"',
    ):
        match = re.search(pattern, res.text)
        if match:
            return match.group(1)
    return None


def fetch_youtube() -> list[dict]:
    videos = _fetch_youtube_pages()
    if not videos:
        log.warning("YouTube 채널 페이지 실패 → RSS로 재시도")
        videos = _fetch_youtube_rss()

    videos.sort(key=lambda item: item["published"], reverse=True)
    videos = videos[: config.YOUTUBE_MAX_ITEMS]
    log.info("YouTube %s개 수집", len(videos))
    return videos


def _relative_time(text: str, now: datetime) -> datetime:
    value = (text or "").lower()
    units = {
        "second": "seconds", "minute": "minutes", "hour": "hours",
        "day": "days", "week": "weeks", "month": "days", "year": "days",
    }
    match = re.search(r"(\d+)\s*(second|minute|hour|day|week|month|year)s?\s+ago", value)
    if not match:
        short = re.search(r"(\d+)\s*(s|m|h|d|w|mo|y)\s+ago", value)
        if short:
            unit_map = {"s": "second", "m": "minute", "h": "hour", "d": "day", "w": "week", "mo": "month", "y": "year"}
            match = short
            match_unit = unit_map[short.group(2)]
        else:
            match_unit = None
    else:
        match_unit = match.group(2)
    if match:
        number = int(match.group(1))
        unit = match_unit or match.group(2)
        if unit == "month":
            number *= 30
        elif unit == "year":
            number *= 365
        return now - timedelta(**{units[unit]: number})

    korean = re.search(r"(\d+)\s*(초|분|시간|일|주|개월|년)\s*전", value)
    if korean:
        number = int(korean.group(1))
        unit = korean.group(2)
        mapping = {"초": "seconds", "분": "minutes", "시간": "hours", "일": "days", "주": "weeks", "개월": "days", "년": "days"}
        if unit == "개월":
            number *= 30
        elif unit == "년":
            number *= 365
        return now - timedelta(**{mapping[unit]: number})
    return now


def _walk_youtube_videos(node, found: list[dict]) -> None:
    if isinstance(node, dict):
        if node.get("contentId") and node.get("contentType") == "LOCKUP_CONTENT_TYPE_VIDEO":
            metadata = node.get("metadata", {}).get("lockupMetadataViewModel", {})
            title = (metadata.get("title") or {}).get("content")
            if title:
                rows = (
                    metadata.get("metadata", {})
                    .get("contentMetadataViewModel", {})
                    .get("metadataRows", [])
                )
                labels = []
                for row in rows:
                    for part in row.get("metadataParts", []):
                        labels.append(part.get("accessibilityLabel") or part.get("text", {}).get("content") or "")
                found.append(
                    {
                        "video_id": node["contentId"],
                        "title": title,
                        "time_label": " ".join(labels),
                    }
                )
        for value in node.values():
            _walk_youtube_videos(value, found)
    elif isinstance(node, list):
        for value in node:
            _walk_youtube_videos(value, found)


def _fetch_youtube_pages() -> list[dict]:
    now = datetime.now(timezone.utc)
    videos: list[dict] = []
    seen: set[str] = set()

    for channel in config.YOUTUBE_CHANNELS:
        if len(videos) >= config.YOUTUBE_MAX_ITEMS:
            break
        handle = channel["handle"]
        channel_videos: list[tuple[datetime, dict, str]] = []

        for tab in ("videos", "shorts"):
            res = http_get(f"https://www.youtube.com/@{handle}/{tab}?hl=en&gl=US")
            if not res:
                log.warning("YouTube 채널 페이지 실패: @%s/%s", handle, tab)
                continue

            marker = res.text.find("ytInitialData = ")
            if marker < 0:
                log.warning("YouTube 초기 데이터 없음: @%s/%s", handle, tab)
                continue
            try:
                data, _ = json.JSONDecoder().raw_decode(res.text[res.text.find("{", marker):])
            except ValueError:
                log.warning("YouTube JSON 파싱 실패: @%s/%s", handle, tab)
                continue

            found: list[dict] = []
            _walk_youtube_videos(data, found)
            for entry in found:
                if entry["video_id"] in seen:
                    continue
                published = _relative_time(entry["time_label"], now)
                if not is_fresh(published, config.YOUTUBE_MAX_AGE_HOURS):
                    continue
                channel_videos.append((published, entry, tab))
            time.sleep(config.REQUEST_DELAY)

        # 최신순. 쇼츠와 일반 영상을 함께 정렬한다.
        channel_videos.sort(key=lambda item: item[0], reverse=True)
        for published, entry, tab in channel_videos[: config.YOUTUBE_MAX_PER_CHANNEL]:
            video_id = entry["video_id"]
            if video_id in seen:
                continue
            seen.add(video_id)
            url = (
                f"https://www.youtube.com/shorts/{video_id}"
                if tab == "shorts"
                else f"https://www.youtube.com/watch?v={video_id}"
            )
            videos.append(
                base_article(
                    source="youtube",
                    title=entry["title"],
                    url=url,
                    published=published,
                    body="",
                    excerpt=entry["title"],
                    author=channel["label"],
                    image=f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
                    lang="en",
                    kind="video",
                )
                | {"video_team": channel["team"], "video_channel": channel["label"]},
            )

    videos.sort(key=lambda item: item["published"], reverse=True)
    return videos


def _fetch_youtube_rss() -> list[dict]:
    cache = _load_channel_cache()
    videos: list[dict] = []

    for channel in config.YOUTUBE_CHANNELS:
        handle = channel["handle"]
        channel_id = cache.get(handle)
        if not channel_id:
            channel_id = _resolve_channel_id(handle)
            if channel_id:
                cache[handle] = channel_id
                time.sleep(config.REQUEST_DELAY)
        if not channel_id:
            log.warning("YouTube 채널 ID 확인 실패: @%s", handle)
            continue

        res = http_get(f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}")
        if not res:
            continue
        feed = feedparser.parse(res.content)

        count = 0
        for entry in feed.entries:
            published = entry_datetime(entry)
            if not is_fresh(published, config.YOUTUBE_MAX_AGE_HOURS):
                continue
            title = entry.get("title", "")
            description = entry.get("media_description") or entry.get("summary", "")
            body = clean_text(description)
            videos.append(
                base_article(
                    source="youtube",
                    title=title,
                    url=entry.get("link", ""),
                    published=published,
                    body=body,
                    excerpt=body[:240],
                    author=entry.get("author", channel["label"]),
                    image=entry.get("media_thumbnail", [{}])[0].get("url"),
                    lang="it",
                    kind="video",
                    comments=[],
                )
                | {"video_team": channel["team"], "video_channel": channel["label"]},
            )
            count += 1
            if count >= config.YOUTUBE_MAX_PER_CHANNEL:
                break

    config.YOUTUBE_CACHE_FILE.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return videos


# --- 실행 -----------------------------------------------------------------
def dedupe_by_url(articles: Iterable[dict]) -> list[dict]:
    seen: set[str] = set()
    result = []
    for article in articles:
        key = article["url"].split("#")[0]
        # YouTube는 ?v=영상ID가 다르므로 쿼리를 보존한다.
        if "youtube.com" not in key:
            key = key.split("?")[0]
        key = key.rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        result.append(article)
    return result


def fetch_all() -> list[dict]:
    started = time.time()
    articles: list[dict] = []

    for name, fetcher_fn in (
        ("rss", fetch_rss_sources),
        ("ultimouomo", fetch_ultimouomo),
        ("history", fetch_history_seeds),
        ("reddit", fetch_reddit),
        ("youtube", fetch_youtube),
    ):
        try:
            articles.extend(fetcher_fn())
        except Exception:  # 한 소스가 깨져도 나머지는 살린다
            log.exception("%s 수집 중 오류", name)

    articles = dedupe_by_url(articles)
    articles.sort(key=lambda item: item["published"], reverse=True)

    payload = {
        "fetched_at": to_iso(datetime.now(timezone.utc)),
        "count": len(articles),
        "articles": articles,
    }
    config.RAW_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log.info("총 %s개 저장 → %s (%.1fs)", len(articles), config.RAW_FILE, time.time() - started)
    return articles


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    fetch_all()

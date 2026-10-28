"""Reddit OAuth 경로 테스트 (실제 API 호출 없음).

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import json
import os
import time
import unittest
from unittest import mock

import fetcher


class FakeResponse:
    def __init__(self, status_code: int, payload, headers: dict | None = None) -> None:
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}
        self.text = json.dumps(payload) if not isinstance(payload, str) else payload

    def json(self):
        return self._payload


def hot_payload() -> dict:
    now = time.time()
    return {
        "data": {
            "children": [
                {
                    "kind": "t3",
                    "data": {
                        "title": "Post A",
                        "permalink": "/r/seriea/comments/abc/post_a/",
                        "created_utc": now,
                        "num_comments": 5,
                        "selftext": "long analysis post " * 60,
                        "author": "u1",
                        "preview": {"images": [{"source": {"url": "https://i.redd.it/a.jpg"}}]},
                    },
                },
                {
                    "kind": "t3",
                    "data": {
                        "title": "Sticky",
                        "permalink": "/r/seriea/comments/sticky/",
                        "created_utc": now,
                        "num_comments": 99,
                        "stickied": True,
                    },
                },
                {
                    "kind": "t3",
                    "data": {
                        "title": "Old",
                        "permalink": "/r/seriea/comments/old/",
                        "created_utc": now - 999999,
                        "num_comments": 1,
                    },
                },
            ]
        }
    }


def comments_payload() -> list:
    return [
        {"kind": "Listing", "data": {"children": []}},
        {
            "kind": "Listing",
            "data": {
                "children": [
                    {"kind": "t1", "data": {"body": "meme comment", "score": 5, "author": "u2"}},
                    {"kind": "t1", "data": {"body": "top comment", "score": 120, "author": "u3"}},
                    {"kind": "t1", "data": {"body": "[deleted]", "score": 50, "author": "[deleted]"}},
                    {"kind": "t1", "data": {"body": "pinned mod", "score": 200, "author": "mod", "stickied": True}},
                    {"kind": "more", "data": {}},
                ]
            },
        },
    ]


class RedditOAuthTest(unittest.TestCase):
    def test_fetch_long_form_posts_without_comments(self) -> None:
        seen: list[tuple] = []

        def fake_get(url, params=None, headers=None, timeout=None):
            seen.append((url, params, headers))
            if url.endswith("/hot"):
                return FakeResponse(200, hot_payload())
            return FakeResponse(404, {})

        env = {"REDDIT_CLIENT_ID": "cid", "REDDIT_CLIENT_SECRET": "secret"}
        with (
            mock.patch.dict(os.environ, env),
            mock.patch.object(fetcher.requests, "post", return_value=FakeResponse(200, {"access_token": "tok"})),
            mock.patch.object(fetcher.requests, "get", side_effect=fake_get),
            mock.patch.object(fetcher.time, "sleep", return_value=None),
        ):
            posts = fetcher.fetch_reddit()

        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0]["title"], "Post A")
        self.assertEqual(posts[0]["comments"], [])
        self.assertTrue(all(params.get("raw_json") == 1 for _, params, _ in seen))
        self.assertIn("User-Agent", seen[0][2])
        self.assertIn("seriea-feed", seen[0][2]["User-Agent"])

    def test_rate_limit_retry(self) -> None:
        calls = {"count": 0}

        def fake_get(*args, **kwargs):
            calls["count"] += 1
            if calls["count"] == 1:
                return FakeResponse(429, {"error": "rate"}, {"X-Ratelimit-Reset": "1"})
            return FakeResponse(200, {"ok": True})

        with (
            mock.patch.object(fetcher.requests, "get", side_effect=fake_get),
            mock.patch.object(fetcher.time, "sleep") as sleep,
        ):
            result = fetcher._reddit_get("tok", "/r/seriea/hot")

        self.assertEqual(result, {"ok": True})
        self.assertEqual(calls["count"], 2)
        sleep.assert_called_once()

    def test_falls_back_to_rss_without_credentials(self) -> None:
        with (
            mock.patch.dict(os.environ, {"REDDIT_CLIENT_ID": "", "REDDIT_CLIENT_SECRET": ""}),
            mock.patch.object(fetcher, "_fetch_reddit_rss", return_value=[{"id": "rss"}]) as rss,
        ):
            posts = fetcher.fetch_reddit()

        self.assertEqual(posts, [{"id": "rss"}])
        rss.assert_called_once()


if __name__ == "__main__":
    unittest.main()

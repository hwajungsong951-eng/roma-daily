"""경기 결과 자동 갱신 테스트 (TheSportsDB 호출 없음).

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import config
import fixtures

NOW = datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc)


def event(
    home: str,
    away: str,
    home_score,
    away_score,
    *,
    kickoff: str = "2026-10-25T19:45:00",
    round_number: str = "8",
    season: str = "2026-2027",
    status: str = "FT",
) -> dict:
    return {
        "strSeason": season,
        "strStatus": status,
        "strHomeTeam": home,
        "strAwayTeam": away,
        "intHomeScore": home_score,
        "intAwayScore": away_score,
        "strTimestamp": kickoff,
        "intRound": round_number,
    }


class FixturesTest(unittest.TestCase):
    def test_team_mapping(self) -> None:
        self.assertEqual(fixtures.team_id("AC Milan"), "milan")
        self.assertEqual(fixtures.team_id("Inter Milan"), "inter")
        self.assertEqual(fixtures.team_id("Atalanta"), "atalanta")
        self.assertEqual(fixtures.team_id("Hellas Verona"), None)

    def test_parse_events(self) -> None:
        parsed = fixtures.parse_events(
            [
                event("Udinese", "AC Milan", 0, 2),
                event("Inter Milan", "Fiorentina", "2", "1"),
                event("Roma", "Cagliari", None, None, status="NS", kickoff="2026-10-27T19:45:00"),
                event("Hellas Verona", "Bologna", 0, 1),
                event("Genoa", "Venezia", 1, 0, season="2025-2026"),
            ],
            "2026-2027",
            NOW,
        )

        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[0]["home"], "udinese")
        self.assertEqual(parsed[0]["away"], "milan")
        self.assertEqual(parsed[0]["score"], "0-2")
        self.assertEqual(parsed[0]["finished_at"], "2026-10-25T21:45:00Z")
        self.assertEqual(parsed[0]["round"], 8)
        self.assertEqual(parsed[1]["home"], "inter")
        self.assertEqual(parsed[1]["score"], "2-1")

    def test_merge_overrides_and_prunes(self) -> None:
        existing = [
            {
                "home": "atalanta",
                "away": "frosinone",
                "score": "4-4",
                "finished_at": "2026-10-25T16:00:00Z",
                "competition": "Serie A",
            },
            {
                "home": "napoli",
                "away": "roma",
                "score": "3-3",
                "finished_at": "2026-10-24T18:00:00Z",
                "competition": "Serie A",
            },
            {
                "home": "lazio",
                "away": "parma",
                "score": "2-1",
                "finished_at": "2026-10-01T20:45:00Z",
                "competition": "Serie A",
            },
        ]
        new = [
            {
                "home": "atalanta",
                "away": "frosinone",
                "score": "4-4",
                "finished_at": "2026-10-25T16:00:00Z",
                "competition": "Serie A",
                "source": "thesportsdb",
                "round": 8,
            }
        ]

        merged = fixtures.merge_matches(existing, new, NOW)
        self.assertEqual(len(merged), 2)
        by_key = {(match["home"], match["away"]): match for match in merged}
        self.assertEqual(by_key[("atalanta", "frosinone")]["source"], "thesportsdb")
        self.assertEqual(by_key[("napoli", "roma")]["source"], "manual")
        self.assertNotIn(("lazio", "parma"), by_key)

    def test_update_matches_writes_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "matches.json"
            before = [
                {
                    "home": "napoli",
                    "away": "roma",
                    "score": "3-3",
                    "finished_at": "2026-10-24T18:00:00Z",
                    "competition": "Serie A",
                }
            ]
            path.write_text(json.dumps(before), encoding="utf-8")

            def fake_round(season: str, round_number: int) -> list[dict]:
                if round_number == 8:
                    return [event("AC Milan", "Udinese", 2, 0, kickoff="2026-10-25T19:45:00")]
                return []

            with (
                mock.patch.object(config, "MATCHES_FILE", path),
                mock.patch.object(fixtures, "_anchor_round", return_value=9),
                mock.patch.object(fixtures, "_fetch_round", side_effect=fake_round),
            ):
                merged = fixtures.update_matches(now=NOW)

            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(len(saved), 2)
            self.assertEqual(len(merged), 2)
            self.assertTrue(any(match["source"] == "thesportsdb" for match in saved))

    def test_failure_keeps_existing_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "matches.json"
            original = [{"home": "inter", "away": "milan", "score": "1-0", "finished_at": "2026-10-25T20:45:00Z"}]
            path.write_text(json.dumps(original), encoding="utf-8")

            with (
                mock.patch.object(config, "MATCHES_FILE", path),
                mock.patch.object(fixtures, "_anchor_round", return_value=None),
            ):
                fixtures.update_matches(now=NOW)

            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), original)

    def test_current_season(self) -> None:
        self.assertEqual(fixtures.current_season(datetime(2026, 10, 26, tzinfo=timezone.utc)), "2026-2027")
        self.assertEqual(fixtures.current_season(datetime(2027, 3, 1, tzinfo=timezone.utc)), "2026-2027")
        self.assertEqual(fixtures.current_season(datetime(2027, 7, 1, tzinfo=timezone.utc)), "2027-2028")


if __name__ == "__main__":
    unittest.main()

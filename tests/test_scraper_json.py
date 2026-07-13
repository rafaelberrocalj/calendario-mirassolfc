import unittest
from datetime import datetime

from scraper import MirassolScraper


def build_summary(
    *,
    date="2026-05-16T21:30Z",
    completed=False,
    status_detail="5/16 - 18:30",
    time_valid=None,
    home_score=None,
    away_score=None,
    league_name="2026 Campeonato Brasileiro",
):
    competition = {
        "date": date,
        "competitors": [
            {
                "homeAway": "home",
                "team": {"displayName": "Mirassol"},
                "score": home_score,
            },
            {
                "homeAway": "away",
                "team": {"displayName": "Santos"},
                "score": away_score,
            },
        ],
        "status": {
            "type": {
                "completed": completed,
                "description": "Finalizado" if completed else "Agendado",
                "detail": status_detail,
                "shortDetail": "F" if completed else status_detail,
            }
        },
    }
    if time_valid is not None:
        competition["timeValid"] = time_valid

    return {
        "header": {
            "league": {"name": league_name},
            "competitions": [competition],
        }
    }


class FakeJsonScraper(MirassolScraper):
    def __init__(self, responses):
        self.games = []
        self.responses = responses

    def fetch_json(self, url):
        for key, value in self.responses.items():
            if key in url:
                return value
        raise AssertionError(f"URL inesperada: {url}")


class ScraperJsonTests(unittest.TestCase):
    def test_parse_finished_event_with_score(self):
        scraper = MirassolScraper.__new__(MirassolScraper)
        game = scraper.parse_json_event(
            build_summary(
                completed=True,
                status_detail="Finalizado",
                home_score="2",
                away_score="1",
            ),
            event_id="evt-1",
        )

        self.assertEqual(game["status"], "finished")
        self.assertTrue(game["all_day"])
        self.assertEqual(game["score"], "2 - 1")
        self.assertEqual(game["championship"], "Campeonato Brasileiro")
        self.assertEqual(game["date"], datetime(2026, 5, 16, 0, 0))

    def test_parse_scheduled_event_with_defined_time(self):
        scraper = MirassolScraper.__new__(MirassolScraper)
        game = scraper.parse_json_event(build_summary(), event_id="evt-2")

        self.assertEqual(game["status"], "scheduled")
        self.assertFalse(game["all_day"])
        self.assertEqual(game["time"], "18:30")
        self.assertIsNone(game["score"])

    def test_parse_scheduled_event_with_undefined_time_as_all_day(self):
        scraper = MirassolScraper.__new__(MirassolScraper)
        game = scraper.parse_json_event(
            build_summary(status_detail="12/2 - A definir"),
            event_id="evt-3",
        )

        self.assertEqual(game["status"], "scheduled")
        self.assertTrue(game["all_day"])
        self.assertEqual(game["time"], "00:00")

    def test_json_scrape_deduplicates_same_event_across_leagues(self):
        list_payload = {
            "items": [
                {
                    "$ref": (
                        "http://sports.core.api.espn.com/v2/sports/soccer/"
                        "leagues/bra.1/events/401?lang=pt&region=br"
                    )
                }
            ]
        }
        scraper = FakeJsonScraper(
            {
                "/teams/9169/events": list_payload,
                "summary?event=401": build_summary(),
            }
        )

        scraper.scrape_json_api(year=2026)

        self.assertEqual(len(scraper.games), 1)
        self.assertEqual(scraper.games[0]["event_id"], "401")

    def test_stable_event_uid_prefers_espn_event_id(self):
        scraper = MirassolScraper.__new__(MirassolScraper)
        game = {
            "date": datetime(2026, 7, 17, 0, 0),
            "team1": "Mirassol",
            "team2": "Grêmio",
            "championship": "Campeonato Brasileiro",
            "event_id": "401841155",
        }

        self.assertEqual(scraper._stable_event_uid(game), "espn-401841155")

        game["date"] = datetime(2026, 7, 18, 0, 0)
        self.assertEqual(scraper._stable_event_uid(game), "espn-401841155")


if __name__ == "__main__":
    unittest.main()

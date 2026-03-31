import unittest
from datetime import date, datetime

import icalendar

from calendar_utils import EventManager


class FakeRequest:
    def __init__(self, payload):
        self.payload = payload

    def execute(self):
        return self.payload


class FakeEventsResource:
    def __init__(self):
        self.items = []
        self.next_id = 1

    def list(
        self,
        calendarId,
        maxResults=2500,
        pageToken=None,
        singleEvents=False,
    ):
        return FakeRequest({"items": list(self.items)})

    def insert(self, calendarId, body):
        event = dict(body)
        event["id"] = f"evt-{self.next_id}"
        self.next_id += 1
        self.items.append(event)
        return FakeRequest(event)

    def update(self, calendarId, eventId, body):
        for index, event in enumerate(self.items):
            if event["id"] == eventId:
                updated = dict(body)
                updated["id"] = eventId
                self.items[index] = updated
                return FakeRequest(updated)
        raise AssertionError(f"Evento não encontrado para update: {eventId}")


class FakeCalendarService:
    def __init__(self):
        self.events_resource = FakeEventsResource()

    def events(self):
        return self.events_resource


def build_vevent(uid, summary, description, start_value, end_value):
    event = icalendar.Event()
    event.add("uid", uid)
    event.add("summary", summary)
    event.add("description", description)
    event.add("dtstart", start_value)
    event.add("dtend", end_value)
    return event


class EventSyncTests(unittest.TestCase):
    def setUp(self):
        self.service = FakeCalendarService()
        self.manager = EventManager(service=self.service)
        self.calendar_id = "test-calendar"

    def test_upload_events_updates_existing_events_without_duplication(self):
        original_event = build_vevent(
            "abc123@mirassol.local",
            "Mirassol x Santos - Paulista",
            "Paulista - Jogo agendado",
            datetime(2026, 4, 1, 19, 0),
            datetime(2026, 4, 1, 21, 0),
        )
        updated_event = build_vevent(
            "abc123@mirassol.local",
            "Mirassol x Santos - Brasileirao",
            "Brasileirao - Jogo agendado",
            datetime(2026, 4, 1, 19, 30),
            datetime(2026, 4, 1, 21, 30),
        )

        first_success, first_failed = self.manager.upload_events(
            self.calendar_id, [original_event]
        )
        second_success, second_failed = self.manager.upload_events(
            self.calendar_id, [updated_event]
        )

        self.assertEqual((first_success, first_failed), (1, 0))
        self.assertEqual((second_success, second_failed), (1, 0))
        self.assertEqual(len(self.service.events_resource.items), 1)

        stored_event = self.service.events_resource.items[0]
        self.assertEqual(stored_event["summary"], "Mirassol x Santos - Brasileirao")
        self.assertEqual(
            stored_event["extendedProperties"]["private"]["mirassol_uid"],
            "abc123@mirassol.local",
        )
        self.assertEqual(
            stored_event["start"]["dateTime"], "2026-04-01T19:30:00-03:00"
        )

    def test_upload_events_matches_legacy_events_without_uid_metadata(self):
        legacy_event = {
            "id": "legacy-1",
            "summary": "Mirassol x Bahia - Copa",
            "description": "Copa - Jogo agendado",
            "start": {"date": "2026-05-01"},
            "end": {"date": "2026-05-02"},
        }
        self.service.events_resource.items.append(legacy_event)

        vevent = build_vevent(
            "legacy@mirassol.local",
            "Mirassol x Bahia - Copa",
            "Copa - Jogo agendado",
            date(2026, 5, 1),
            date(2026, 5, 2),
        )

        success, failed = self.manager.upload_events(self.calendar_id, [vevent])

        self.assertEqual((success, failed), (1, 0))
        self.assertEqual(len(self.service.events_resource.items), 1)
        stored_event = self.service.events_resource.items[0]
        self.assertEqual(stored_event["id"], "legacy-1")
        self.assertEqual(
            stored_event["extendedProperties"]["private"]["mirassol_uid"],
            "legacy@mirassol.local",
        )


if __name__ == "__main__":
    unittest.main()

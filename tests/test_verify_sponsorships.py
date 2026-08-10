import copy
import unittest
from datetime import datetime, timezone

from scripts.verify_sponsorships import SponsorshipValidationError, validate

NOW = datetime(2026, 8, 11, 0, 0, tzinfo=timezone.utc)


def event_payload():
    return {
        "events": [
            {
                "id": "event-001",
                "title": "Synthetic public event",
                "official_url": "https://example.com/events/001",
                "participation_url": "https://example.com/events/001/join",
            }
        ]
    }


def campaign_payload():
    return {
        "schema_version": "featured-tonight.v1",
        "campaigns": [
            {
                "campaign_id": "demo-001",
                "event_id": "event-001",
                "sponsor_name": "Synthetic Organizer",
                "starts_at": "2026-08-10T00:00:00Z",
                "ends_at": "2026-08-16T00:00:00Z",
                "status": "APPROVED",
                "approved_at": "2026-08-09T00:00:00Z",
                "destination_url": "https://example.com/events/001",
                "authorization_status": "VERIFIED",
                "authorization_evidence_url": "https://example.com/events/001/authorization",
            }
        ],
    }


class SponsorshipValidationTests(unittest.TestCase):
    def test_valid_campaign_is_active(self):
        result = validate(campaign_payload(), event_payload(), now=NOW)
        self.assertEqual(result["campaign_count"], 1)
        self.assertEqual(result["active_campaign_count"], 1)

    def test_event_must_exist(self):
        payload = campaign_payload()
        payload["campaigns"][0]["event_id"] = "missing"
        with self.assertRaisesRegex(SponsorshipValidationError, "event not found"):
            validate(payload, event_payload(), now=NOW)

    def test_destination_must_match_event(self):
        payload = campaign_payload()
        payload["campaigns"][0]["destination_url"] = "https://example.net/unrelated"
        with self.assertRaisesRegex(SponsorshipValidationError, "must match event"):
            validate(payload, event_payload(), now=NOW)

    def test_campaign_cannot_exceed_seven_days(self):
        payload = campaign_payload()
        payload["campaigns"][0]["ends_at"] = "2026-08-18T00:00:01Z"
        with self.assertRaisesRegex(SponsorshipValidationError, "exceeds 7 days"):
            validate(payload, event_payload(), now=NOW)

    def test_authorization_is_required(self):
        payload = campaign_payload()
        payload["campaigns"][0]["authorization_status"] = "UNVERIFIED"
        with self.assertRaisesRegex(SponsorshipValidationError, "VERIFIED required"):
            validate(payload, event_payload(), now=NOW)

    def test_expired_approved_campaign_fails_closed(self):
        payload = campaign_payload()
        with self.assertRaisesRegex(SponsorshipValidationError, "expired APPROVED"):
            validate(payload, event_payload(), now=datetime(2026, 8, 16, tzinfo=timezone.utc))

    def test_expired_status_is_not_renderable_but_remains_auditable(self):
        payload = campaign_payload()
        payload["campaigns"][0]["status"] = "EXPIRED"
        result = validate(payload, event_payload(), now=datetime(2026, 8, 20, tzinfo=timezone.utc))
        self.assertEqual(result["active_campaign_count"], 0)

    def test_duplicate_campaign_id_is_rejected(self):
        payload = campaign_payload()
        payload["campaigns"].append(copy.deepcopy(payload["campaigns"][0]))
        with self.assertRaisesRegex(SponsorshipValidationError, "duplicate"):
            validate(payload, event_payload(), now=NOW)


if __name__ == "__main__":
    unittest.main()

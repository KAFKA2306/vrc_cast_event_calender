#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

CAMPAIGN_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
SCHEMA_VERSION = "featured-tonight.v1"
ACTIVE_STATUS = "APPROVED"
STATUSES = {ACTIVE_STATUS, "PAUSED", "EXPIRED"}
URL_FIELDS = (
    "official_url",
    "source_url",
    "announcement_url",
    "url",
    "tweet_url",
    "join_url",
    "participation_url",
    "group_url",
    "request_url",
)


class SponsorshipValidationError(ValueError):
    pass


def parse_datetime(value: object, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise SponsorshipValidationError(f"{field}: non-empty ISO 8601 value required")
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise SponsorshipValidationError(f"{field}: invalid ISO 8601 datetime") from exc
    if parsed.tzinfo is None:
        raise SponsorshipValidationError(f"{field}: timezone offset required")
    return parsed.astimezone(timezone.utc)


def valid_https_url(value: object) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)


def event_records(payload: object) -> list[dict]:
    if isinstance(payload, list):
        records = payload
    elif isinstance(payload, dict) and isinstance(payload.get("events"), list):
        records = payload["events"]
    else:
        raise SponsorshipValidationError("events: expected array or object.events array")
    if not all(isinstance(item, dict) for item in records):
        raise SponsorshipValidationError("events: every record must be an object")
    return records


def event_id(event: dict) -> str:
    for key in ("id", "event_id", "slug", "source_url"):
        value = event.get(key)
        if value is not None and str(value).strip():
            return str(value)
    for key in ("title", "name", "event_name"):
        value = event.get(key)
        if value is not None and str(value).strip():
            return str(value)
    return ""


def allowed_destinations(event: dict) -> set[str]:
    return {
        str(event[key]).strip()
        for key in URL_FIELDS
        if key in event and valid_https_url(event[key])
    }


def validate(payload: object, events_payload: object, *, now: datetime) -> dict:
    if not isinstance(payload, dict):
        raise SponsorshipValidationError("manifest: object required")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise SponsorshipValidationError(f"schema_version: expected {SCHEMA_VERSION}")
    campaigns = payload.get("campaigns")
    if not isinstance(campaigns, list):
        raise SponsorshipValidationError("campaigns: array required")

    events = event_records(events_payload)
    indexed: dict[str, dict] = {}
    for event in events:
        eid = event_id(event)
        if eid:
            if eid in indexed:
                raise SponsorshipValidationError(f"events: duplicate event id {eid}")
            indexed[eid] = event

    seen: set[str] = set()
    active_count = 0
    for pos, campaign in enumerate(campaigns):
        prefix = f"campaigns[{pos}]"
        if not isinstance(campaign, dict):
            raise SponsorshipValidationError(f"{prefix}: object required")

        cid = campaign.get("campaign_id")
        if not isinstance(cid, str) or not CAMPAIGN_ID.fullmatch(cid):
            raise SponsorshipValidationError(f"{prefix}.campaign_id: invalid")
        if cid in seen:
            raise SponsorshipValidationError(f"{prefix}.campaign_id: duplicate {cid}")
        seen.add(cid)

        eid = campaign.get("event_id")
        if not isinstance(eid, str) or not eid.strip() or eid not in indexed:
            raise SponsorshipValidationError(f"{prefix}.event_id: event not found")
        event = indexed[eid]

        sponsor_name = campaign.get("sponsor_name")
        if not isinstance(sponsor_name, str) or not sponsor_name.strip():
            raise SponsorshipValidationError(f"{prefix}.sponsor_name: non-empty value required")

        status = campaign.get("status")
        if status not in STATUSES:
            raise SponsorshipValidationError(f"{prefix}.status: invalid")

        starts_at = parse_datetime(campaign.get("starts_at"), f"{prefix}.starts_at")
        ends_at = parse_datetime(campaign.get("ends_at"), f"{prefix}.ends_at")
        approved_at = parse_datetime(campaign.get("approved_at"), f"{prefix}.approved_at")
        if ends_at <= starts_at:
            raise SponsorshipValidationError(f"{prefix}: ends_at must be after starts_at")
        if (ends_at - starts_at).total_seconds() > 7 * 24 * 60 * 60:
            raise SponsorshipValidationError(f"{prefix}: campaign exceeds 7 days")
        if approved_at > ends_at:
            raise SponsorshipValidationError(f"{prefix}: approved_at must not be after ends_at")

        destination = campaign.get("destination_url")
        if not valid_https_url(destination):
            raise SponsorshipValidationError(f"{prefix}.destination_url: HTTPS URL required")
        if destination not in allowed_destinations(event):
            raise SponsorshipValidationError(
                f"{prefix}.destination_url: must match event official/participation URL"
            )

        if campaign.get("authorization_status") != "VERIFIED":
            raise SponsorshipValidationError(f"{prefix}.authorization_status: VERIFIED required")
        if not valid_https_url(campaign.get("authorization_evidence_url")):
            raise SponsorshipValidationError(
                f"{prefix}.authorization_evidence_url: HTTPS evidence URL required"
            )

        if status == ACTIVE_STATUS:
            if now >= ends_at:
                raise SponsorshipValidationError(
                    f"{prefix}: expired APPROVED campaign must be marked EXPIRED or removed"
                )
            if starts_at <= now < ends_at:
                active_count += 1

    return {
        "schema_version": SCHEMA_VERSION,
        "campaign_count": len(campaigns),
        "active_campaign_count": active_count,
        "event_count": len(events),
        "validated_at": now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def load_json(path: Path) -> object:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", default="events.json")
    parser.add_argument("--sponsorships", default="sponsorships.json")
    parser.add_argument("--now", help="ISO 8601 validation time; defaults to current UTC")
    args = parser.parse_args()

    now = parse_datetime(args.now, "--now") if args.now else datetime.now(timezone.utc)
    result = validate(load_json(Path(args.sponsorships)), load_json(Path(args.events)), now=now)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

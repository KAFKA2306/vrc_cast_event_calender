#!/usr/bin/env python3
"""Fail closed when a deployed projection diverges from its provenance manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

REQUIRED_FIELDS = {
    "schema_version",
    "source_repository",
    "source_commit_sha",
    "source_snapshot_sha256",
    "generated_at",
    "received_at",
    "deployed_at",
    "collection_counts",
    "assets",
    "ontology_version",
    "validation_status",
}
SEARCH_BASE_URL = "https://kafka2306.github.io/vrc_cast_event_calender/"
SEARCH_PAGE_PREFIXES = ("events/", "categories/", "series/")


def snapshot_digest(assets: dict[str, dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for name, metadata in sorted(assets.items()):
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(metadata["bytes"]).encode("ascii"))
        digest.update(b"\0")
        digest.update(metadata["sha256"].encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def verify_search_surface(root: Path, assets: dict[str, dict[str, Any]]) -> None:
    """Validate the derived search surface once a canonical sitemap is present."""
    if "sitemap.xml" not in assets:
        return

    required = {"index.html", "sitemap.xml", "analytics.js", "analytics-config.json"}
    missing = sorted(required - set(assets))
    if missing:
        raise ValueError(f"search surface missing assets: {', '.join(missing)}")

    search_assets = sorted(
        name
        for name in assets
        if name.startswith(SEARCH_PAGE_PREFIXES) and name.endswith("/index.html")
    )
    detail_assets = [name for name in search_assets if name.startswith("events/")]
    if not detail_assets:
        raise ValueError("search surface has no event detail pages")

    sitemap = ET.parse(root / "sitemap.xml").getroot()
    namespace = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls = [node.text for node in sitemap.findall("s:url/s:loc", namespace)]
    if any(not isinstance(url, str) or not url.startswith(SEARCH_BASE_URL) for url in urls):
        raise ValueError("sitemap contains a non-canonical URL")
    if len(urls) != len(set(urls)):
        raise ValueError("sitemap contains duplicate URLs")
    if not urls or urls[0] != SEARCH_BASE_URL:
        raise ValueError("sitemap must start with the canonical homepage")

    expected_search_urls = {
        SEARCH_BASE_URL + name.removesuffix("index.html") for name in search_assets
    }
    if set(urls[1:]) != expected_search_urls:
        raise ValueError("sitemap/search-page parity mismatch")

    expected_root_links = {name.removesuffix("index.html") for name in search_assets}
    root_html = (root / "index.html").read_text(encoding="utf-8")
    root_links = set(
        re.findall(r'href=["\']((?:events|categories|series)/[^"\']+/)["\']', root_html)
    )
    if root_links != expected_root_links:
        missing_links = sorted(expected_root_links - root_links)
        extra_links = sorted(root_links - expected_root_links)
        raise ValueError(
            "homepage/search-page one-hop parity mismatch: "
            f"missing={missing_links[:5]} extra={extra_links[:5]}"
        )

    for name in search_assets:
        content = (root / name).read_text(encoding="utf-8")
        expected_url = SEARCH_BASE_URL + name.removesuffix("index.html")
        canonical = f'rel="canonical" href="{expected_url}"'
        if canonical not in content:
            raise ValueError(f"missing canonical search URL: {name}")
        if name.startswith("events/") and "application/ld+json" in content:
            raise ValueError(f"unsupported virtual-only Event JSON-LD: {name}")

    config = json.loads((root / "analytics-config.json").read_text(encoding="utf-8"))
    measurement_id = config.get("ga4_measurement_id")
    if measurement_id is not None and (
        not isinstance(measurement_id, str) or not measurement_id.startswith("G-")
    ):
        raise ValueError("invalid GA4 measurement ID")


def verify(root: Path, manifest_path: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("projection manifest must contain an object")
    missing = sorted(REQUIRED_FIELDS - set(manifest))
    if missing:
        raise ValueError("projection manifest missing fields: " + ", ".join(missing))
    if manifest.get("schema_version") != "cast-event.projection-manifest.v2":
        raise ValueError("unsupported projection manifest schema")
    if manifest.get("role") != "projection_only":
        raise ValueError("projection role must be projection_only")
    if manifest.get("source_repository") != "KAFKA2306/cast_event_cal":
        raise ValueError("unexpected canonical repository")
    if manifest.get("validation_status") != "validated":
        raise ValueError("canonical snapshot is not validated")

    assets = manifest.get("assets")
    if not isinstance(assets, dict) or not assets:
        raise ValueError("projection manifest has no assets")
    for name, expected in assets.items():
        if not isinstance(name, str) or name.startswith("/") or ".." in Path(name).parts:
            raise ValueError(f"unsafe asset path: {name!r}")
        if not isinstance(expected, dict):
            raise ValueError(f"invalid asset metadata: {name}")
        expected_bytes = expected.get("bytes")
        expected_hash = expected.get("sha256")
        if isinstance(expected_bytes, bool) or not isinstance(expected_bytes, int) or expected_bytes < 0:
            raise ValueError(f"invalid asset byte count: {name}")
        if not isinstance(expected_hash, str) or len(expected_hash) != 64:
            raise ValueError(f"invalid asset sha256: {name}")
        path = root / name
        if not path.is_file():
            raise ValueError(f"missing deployed asset: {name}")
        raw = path.read_bytes()
        if expected_bytes != len(raw):
            raise ValueError(f"byte mismatch: {name}")
        if expected_hash != hashlib.sha256(raw).hexdigest():
            raise ValueError(f"sha256 mismatch: {name}")

    expected_snapshot = snapshot_digest(assets)
    if manifest.get("source_snapshot_sha256") != expected_snapshot:
        raise ValueError("source_snapshot_sha256 mismatch")

    events = json.loads((root / "events.json").read_text(encoding="utf-8"))
    health = json.loads((root / "health.json").read_text(encoding="utf-8"))
    ontology = json.loads((root / "event-ontology.json").read_text(encoding="utf-8"))
    rows = events.get("events", [])
    if manifest.get("event_count") != len(rows):
        raise ValueError("manifest event_count mismatch")
    if health.get("event_count") != len(rows):
        raise ValueError("health event_count mismatch")
    if ontology.get("source_event_count") != len(rows):
        raise ValueError("ontology event_count mismatch")
    if manifest.get("collection_counts", {}).get("failed_sources") != 0:
        raise ValueError("manifest reports failed sources")

    verify_search_surface(root, assets)

    return {
        "status": "ok",
        "asset_count": len(assets),
        "event_count": len(rows),
        "source_commit_sha": manifest["source_commit_sha"],
        "source_snapshot_sha256": expected_snapshot,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--manifest", required=True)
    args = parser.parse_args()
    result = verify(Path(args.root), Path(args.manifest))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()

"""LLM Evidence pipeline: verified claims extraction, caching, and domain allowlist filtering."""

import contextlib
import json
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict

from alphalens.config import get_settings


class EvidenceSource(BaseModel):
    """Citation source metadata."""

    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    url: str | None = None


class EvidenceClaim(BaseModel):
    """Verified claim statement with audit citations."""

    model_config = ConfigDict(extra="forbid")

    id: str
    claim_text: str
    category: str
    sentiment: str
    source_ids: list[str]
    sources: list[EvidenceSource]
    verified: bool


# Fixture evidence datasets for Nifty 100 constituents
_FIXTURE_EVIDENCE: dict[str, list[dict[str, Any]]] = {
    "RELIANCE.NS": [
        {
            "id": "claim-rel-01",
            "claim_text": (
                "Consumer business EBITDA contribution surpassed 50% "
                "of total consolidated earnings in Q2 FY26."
            ),
            "category": "Operational",
            "sentiment": "Positive",
            "source_ids": ["src-bse-01"],
            "sources": [
                {
                    "id": "src-bse-01",
                    "title": "BSE Filing - Q2 FY26 Financial Statement",
                    "url": "https://www.bseindia.com/filings/reliance_q2fy26.pdf",
                }
            ],
            "verified": True,
        },
        {
            "id": "claim-rel-02",
            "claim_text": (
                "Retail store footprint expanded by 420 net new locations, "
                "bringing total reach to 18,900+ stores."
            ),
            "category": "Growth",
            "sentiment": "Positive",
            "source_ids": ["src-nse-01"],
            "sources": [
                {
                    "id": "src-nse-01",
                    "title": "NSE Investor Presentation FY26",
                    "url": "https://www.nseindia.com/corporate/reliance_presentation.pdf",
                }
            ],
            "verified": True,
        },
        {
            "id": "claim-rel-03",
            "claim_text": "Unverified market rumor concerning overseas chemical asset buyout.",
            "category": "Speculation",
            "sentiment": "Neutral",
            "source_ids": ["src-unverified"],
            "sources": [
                {
                    "id": "src-unverified",
                    "title": "Unverified blog post",
                    "url": "https://random-speculative-blog.com/rumor",
                }
            ],
            "verified": False,
        },
        {
            "id": "claim-rel-04",
            "claim_text": (
                "Refining throughput margins moderated by 80 bps "
                "due to planned maintenance at Jamnagar complex."
            ),
            "category": "Operational",
            "sentiment": "Negative",
            "source_ids": ["src-untrusted-news"],
            "sources": [
                {
                    "id": "src-untrusted-news",
                    "title": "Third-party news portal",
                    "url": "https://thirdparty-news.com/jamnagar",
                }
            ],
            "verified": True,
        },
    ]
}


def filter_source_url(url: str | None) -> str | None:
    """Filter URL against allowed domains; return None if domain is not on allowlist."""
    if not url:
        return None

    settings = get_settings()
    try:
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower()
        for allowed in settings.allowed_evidence_domains:
            if hostname == allowed or hostname.endswith("." + allowed):
                return url
        return None
    except Exception:
        return None


def get_verified_evidence_claims(ticker: str) -> list[EvidenceClaim]:
    """Retrieve verified claims from daily cache or precomputed pipeline, sanitizing source URLs."""
    settings = get_settings()
    cache_file = settings.cache_dir / f"evidence_{ticker}_daily.json"

    raw_claims: list[dict[str, Any]]
    if cache_file.is_file():
        try:
            raw_claims = json.loads(cache_file.read_text(encoding="utf-8"))
        except Exception:
            raw_claims = _FIXTURE_EVIDENCE.get(ticker, [])
    else:
        raw_claims = _FIXTURE_EVIDENCE.get(ticker, [])
        # Write to daily cache
        settings.cache_dir.mkdir(parents=True, exist_ok=True)
        with contextlib.suppress(Exception):
            cache_file.write_text(json.dumps(raw_claims), encoding="utf-8")

    verified_claims: list[EvidenceClaim] = []
    for item in raw_claims:
        # Rule: Only claims that passed verification are sent
        if not item.get("verified", False):
            continue

        sanitized_sources: list[EvidenceSource] = []
        for src in item.get("sources", []):
            sanitized_sources.append(
                EvidenceSource(
                    id=src["id"],
                    title=src["title"],
                    url=filter_source_url(src.get("url")),
                )
            )

        verified_claims.append(
            EvidenceClaim(
                id=item["id"],
                claim_text=item["claim_text"],
                category=item["category"],
                sentiment=item["sentiment"],
                source_ids=item["source_ids"],
                sources=sanitized_sources,
                verified=True,
            )
        )

    return verified_claims

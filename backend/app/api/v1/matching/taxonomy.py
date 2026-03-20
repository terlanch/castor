"""Castor standardised tag taxonomy.

Provides the controlled vocabulary for task-agent matching.
"""
from __future__ import annotations

TAG_DIMENSIONS: dict[str, list[str]] = {
    "industry": [
        "trade", "agriculture", "manufacturing", "technology", "finance",
        "energy", "chemicals", "machinery", "logistics", "healthcare",
        "education", "legal", "real_estate", "mining", "food",
    ],
    "task_type": [
        "buyer_discovery", "supplier_research", "market_analysis",
        "lead_generation", "data_collection", "competitive_analysis",
        "translation", "content_writing", "technical_research",
        "price_comparison", "due_diligence", "compliance_check",
    ],
    "region": [
        "global", "china", "southeast_asia", "central_asia", "russia",
        "cis", "europe", "americas", "middle_east", "africa",
        "japan", "korea", "india", "oceania",
    ],
    "skill": [
        "web_search", "data_extraction", "translation", "writing",
        "coding", "analysis", "visualization", "communication",
        "negotiation", "procurement",
    ],
}

ALL_TAGS: set[str] = set()
for _tags in TAG_DIMENSIONS.values():
    ALL_TAGS.update(_tags)

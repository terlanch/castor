"""LLM-based task understanding layer.

Calls an OpenAI-compatible chat completions endpoint to convert a
natural-language task description into structured Castor task fields.

Falls back to a simple heuristic when no LLM API key is configured.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from ....config import (
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_JSON_OBJECT_MODE,
    LLM_MODEL,
)
from .taxonomy import TAG_DIMENSIONS

logger = logging.getLogger("castor.llm")

# ── System prompt for the LLM ──────────────────────────────────────────

_SYSTEM_PROMPT = f"""\
You are the task-structuring engine for Castor, an AI labour marketplace.

Given a user's free-form task description, output a JSON object with:

{{
  "category":            "<one of: {', '.join(TAG_DIMENSIONS['task_type'])}; or 'general'>",
  "title":               "<short title, ≤60 chars>",
  "tags":                ["<list of tags from the taxonomy below>"],
  "skills_required":     ["<subset of skill tags>"],
  "region":              "<one of: {', '.join(TAG_DIMENSIONS['region'])}>",
  "constraints":         ["<list of constraints>"],
  "deliverable_format":  "<json | markdown | text>",
  "deliverable_description": "<what the output should contain>",
  "acceptance_criteria": ["<list of acceptance criteria>"]
}}

Tag taxonomy (pick only from these):
- industry: {', '.join(TAG_DIMENSIONS['industry'])}
- task_type: {', '.join(TAG_DIMENSIONS['task_type'])}
- region: {', '.join(TAG_DIMENSIONS['region'])}
- skill: {', '.join(TAG_DIMENSIONS['skill'])}

Rules:
1. Only use tags that exist in the taxonomy above.
2. If the region cannot be determined, default to "global".
3. If the category cannot be determined, default to "general".
4. Output valid JSON only – no markdown fences, no explanation.
"""


def structurize_task(description: str, max_budget: int) -> dict[str, Any]:
    """Convert free-form text → structured task fields.

    Tries LLM first; falls back to simple heuristic on failure or when
    ``CASTOR_LLM_API_KEY`` is not set.
    """
    if LLM_API_KEY:
        try:
            return _call_llm(description, max_budget)
        except Exception:
            logger.exception("LLM structuring failed, falling back to heuristic")
    return _simple_fallback(description, max_budget)


# ── LLM call ───────────────────────────────────────────────────────────

def _call_llm(description: str, max_budget: int) -> dict[str, Any]:
    url = f"{LLM_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
    }
    body: dict[str, Any] = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": description},
        ],
        "temperature": 0.2,
    }
    if LLM_JSON_OBJECT_MODE:
        body["response_format"] = {"type": "json_object"}

    with httpx.Client(timeout=30) as client:
        resp = client.post(url, headers=headers, json=body)
        resp.raise_for_status()

    data = resp.json()
    content = data["choices"][0]["message"]["content"]
    parsed = json.loads(content)

    # Normalise into our standard shape
    return _normalise_llm_output(parsed, description, max_budget)


def _normalise_llm_output(
    raw: dict[str, Any], description: str, max_budget: int
) -> dict[str, Any]:
    """Ensure the LLM output has all required keys with sane defaults."""
    tags = raw.get("tags", [])
    skill_tags = set(TAG_DIMENSIONS.get("skill", []))
    return {
        "category": raw.get("category", "general"),
        "title": (raw.get("title") or description[:57] + "...")[:60],
        "goal": description.strip(),
        "tags": tags,
        "skills_required": raw.get("skills_required", [t for t in tags if t in skill_tags]),
        "region": raw.get("region", "global"),
        "constraints": raw.get("constraints", []),
        "deliverable": {
            "format": raw.get("deliverable_format", "json"),
            "description": raw.get("deliverable_description", f"Structured deliverable for '{description[:40]}'"),
        },
        "acceptance_criteria": raw.get("acceptance_criteria", []),
        "reward": max_budget,
        "sla_seconds": 3600,
    }


# ── Simple fallback (no LLM) ──────────────────────────────────────────

def _simple_fallback(description: str, max_budget: int) -> dict[str, Any]:
    """Minimal structuring when LLM is unavailable."""
    title = description.strip().replace("\n", " ")
    if len(title) > 60:
        title = title[:57] + "..."
    return {
        "category": "general",
        "title": title,
        "goal": description.strip(),
        "tags": [],
        "skills_required": [],
        "region": "global",
        "constraints": ["Prioritize real and verifiable information"],
        "deliverable": {
            "format": "json",
            "description": f"Structured deliverable for '{title}'",
        },
        "acceptance_criteria": ["The result is relevant to the task description", "Data is complete and properly formatted"],
        "reward": max_budget,
        "sla_seconds": 3600,
    }

from typing import Dict, List, Optional

PREDEFINED_TASKS: Dict[str, Dict[str, str]] = {
    "password_reset_count": {
        "intent": "RESET_COUNT",
        "prompt": "How many users need password reset?",
    },
    "password_reset_list": {
        "intent": "RESET_LIST",
        "prompt": "List users who need password reset.",
    },
    "recent_exposed_count": {
        "intent": "RECENT_EXPOSED_COUNT",
        "prompt": "How many users were exposed in the last 6 months?",
    },
    "recent_exposed_list": {
        "intent": "RECENT_EXPOSED_LIST",
        "prompt": "List users exposed in the last 6 months.",
    },
    "source_breakdown": {
        "intent": "SOURCE_BREAKDOWN",
        "prompt": "Show exposure breakdown by source.",
    },
}

DEFAULT_DAILY_TASKS: List[str] = [
    "password_reset_count",
    "recent_exposed_count",
    "source_breakdown",
]


def _normalize(text: str) -> str:
    return " ".join(text.lower().strip().split())


def _resolve_keyword_intent(normalized_query: str) -> Optional[str]:
    query = normalized_query

    if "reset" in query:
        if any(token in query for token in ["count", "how many", "number"]):
            return "RESET_COUNT"
        if any(token in query for token in ["list", "show", "who", "users"]):
            return "RESET_LIST"

    if any(token in query for token in ["recent", "last 6 months", "6 months", "exposed"]):
        if any(token in query for token in ["count", "how many", "number"]):
            return "RECENT_EXPOSED_COUNT"
        if any(token in query for token in ["list", "show", "who", "users"]):
            return "RECENT_EXPOSED_LIST"

    if "source" in query and any(token in query for token in ["breakdown", "distribution", "split"]):
        return "SOURCE_BREAKDOWN"

    return None


def resolve_predefined_intent(task_or_prompt: str) -> Optional[str]:
    normalized_text = _normalize(task_or_prompt)
    normalized_key = normalized_text.replace(" ", "_")
    if normalized_key in PREDEFINED_TASKS:
        return PREDEFINED_TASKS[normalized_key]["intent"]

    prompt_lookup = {
        _normalize(meta["prompt"]): meta["intent"]
        for meta in PREDEFINED_TASKS.values()
    }
    prompt_match = prompt_lookup.get(normalized_text)
    if prompt_match:
        return prompt_match

    return _resolve_keyword_intent(normalized_text)


def get_daily_prompt_template(task_keys: Optional[List[str]] = None) -> str:
    selected = task_keys or DEFAULT_DAILY_TASKS
    lines = [
        "Use ONLY one task key from this list for daily reports:",
    ]

    for key in selected:
        if key in PREDEFINED_TASKS:
            lines.append(f"- {key}: {PREDEFINED_TASKS[key]['prompt']}")

    return "\n".join(lines)

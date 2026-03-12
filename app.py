import json
import os
import re
from typing import List, Optional, Tuple

from Chains.intent_classifier import intent_chain, analysis_chain
from Chains.response_formatter import formatter_chain
from Backend.loader import load_current_batch, load_master_data
from Backend.predefined_tasks import (
    DEFAULT_DAILY_TASKS,
    get_daily_prompt_template,
    resolve_predefined_intent,
)
from Backend.rules import (
    calculate_password_reset_candidates,
    get_exposure_breakdown_by_source,
    get_password_reset_count,
    get_recently_exposed_users,
)

DATA_DIR = "Data"
CURRENT_BATCH_PATH = os.path.join(DATA_DIR, "current_batch.xlsx")
MASTER_DATA_PATH = os.path.join(DATA_DIR, "master_data.xlsx")
CACHE_PATH = os.path.join(DATA_DIR, "format_cache.json")

# Load data ONCE
current_df = load_current_batch(CURRENT_BATCH_PATH)
master_df = load_master_data(MASTER_DATA_PATH)


def _load_format_cache() -> dict:
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_format_cache(cache: dict) -> None:
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def _local_format(text: str) -> str:
    header = "--- Report ---"
    footer = "--- End ---"
    body = text.strip()
    return f"{header}\n{body}\n{footer}"


def _safe_format(task_name: Optional[str], text: str) -> str:
    cache = _load_format_cache()
    if task_name and task_name in cache:
        return cache[task_name]

    # Avoid LLM calls at runtime; return local formatted fallback
    return _local_format(text)


def _extract_source_from_query(query: str) -> Optional[str]:
    """Extract source name from query (e.g., 'BK', 'SSC', 'XMC', 'Bitnight', etc.)."""
    query_upper = query.upper()
    
    # Get all unique sources from data
    sources = set(current_df["source"].unique()) | set(master_df["source"].unique())
    
    # Check for exact source matches
    for source in sources:
        if source.upper() in query_upper:
            return source
    
    # Check for common abbreviations/variations
    abbreviations = {
        "BK": "BK",
        "SSC": "SSC",
        "XMC": "XMC",
        "BITNIGHT": "Bitnight",  # Adjust case as needed
    }
    
    for abbr, full_name in abbreviations.items():
        if abbr in query_upper:
            return full_name
    
    return None


def _extract_intent_keywords(query: str) -> Tuple[bool, bool]:
    """Extract whether query wants a count or list/details.
    Returns (wants_count, wants_list)"""
    query_lower = query.lower()
    
    wants_count = any(keyword in query_lower for keyword in [
        "how many", "count", "total", "number of", "how much"
    ])
    
    wants_list = any(keyword in query_lower for keyword in [
        "list", "show", "give", "who", "which", "names", "users", "details"
    ])
    
    wants_reset = any(keyword in query_lower for keyword in [
        "reset", "password"
    ])
    
    wants_exposed = any(keyword in query_lower for keyword in [
        "exposed", "recent", "exposure"
    ])
    
    return wants_count, wants_list, wants_reset, wants_exposed


def _get_raw_output_for_intent(intent: str) -> Optional[str]:
    if intent == "RESET_COUNT":
        result = get_password_reset_count(current_df, master_df)
        return f"Users needing password reset: {result}"

    if intent == "RESET_LIST":
        df = calculate_password_reset_candidates(current_df, master_df)
        return df.to_string(index=False)

    if intent == "RECENT_EXPOSED_COUNT":
        df = get_recently_exposed_users(current_df, master_df)
        return f"Recently exposed users count: {len(df)}"

    if intent == "RECENT_EXPOSED_LIST":
        df = get_recently_exposed_users(current_df, master_df)
        return df.to_string(index=False)

    if intent == "SOURCE_BREAKDOWN":
        df = get_recently_exposed_users(current_df, master_df)
        breakdown = get_exposure_breakdown_by_source(df)
        return str(breakdown)

    return None


def _prepare_filtered_data_context(source: Optional[str], wants_reset: bool, wants_exposed: bool) -> str:
    """Prepare targeted data context based on extracted intent."""
    
    # Filter data by source if specified
    if source:
        filtered_current = current_df[current_df["source"] == source]
        filtered_master = master_df[master_df["source"] == source]
    else:
        filtered_current = current_df
        filtered_master = master_df
    
    # Calculate relevant metrics
    reset_candidates = calculate_password_reset_candidates(filtered_current, filtered_master) if wants_reset else None
    recent_exposed = get_recently_exposed_users(filtered_current, filtered_master) if wants_exposed else None
    
    # Build context
    context_parts = []
    
    if source:
        context_parts.append(f"Data filtered for source: {source}")
    
    context_parts.append(f"Current batch: {len(filtered_current)} records")
    context_parts.append(f"Master data: {len(filtered_master)} records")
    
    if wants_reset and reset_candidates is not None:
        context_parts.append(f"\nPassword Reset Candidates ({len(reset_candidates)} users):")
        context_parts.append(reset_candidates[["email"]].head(20).to_string(index=False))
    
    if wants_exposed and recent_exposed is not None:
        context_parts.append(f"\nRecently Exposed Users ({len(recent_exposed)} users):")
        context_parts.append(recent_exposed[["email", "source"]].head(20).to_string(index=False))
    
    if filtered_current.empty and filtered_master.empty:
        context_parts.append("No data found for the specified criteria.")
    
    return "\n".join(context_parts)


def _execute_intent(intent: str, task_name: Optional[str] = None):
    raw = _get_raw_output_for_intent(intent)
    if raw is None:
        return "Unsupported query. Allowed questions relate to exposure analysis only."

    return _safe_format(task_name, raw)


def _handle_generic_query(user_query: str) -> str:
    """Handle arbitrary questions with intelligent filtering."""
    try:
        # Extract parameters from query
        source = _extract_source_from_query(user_query)
        wants_count, wants_list, wants_reset, wants_exposed = _extract_intent_keywords(user_query)
        
        # If query mentions "reset" but not "exposed", assume password reset intent
        if wants_reset and not wants_exposed:
            wants_reset = True
            wants_exposed = False
        # If query mentions "exposed" but not "reset", assume exposure intent
        elif wants_exposed and not wants_reset:
            wants_reset = False
            wants_exposed = True
        # Default to reset if reset mentioned but nothing else
        elif wants_reset and not wants_exposed:
            wants_exposed = False
        else:
            # Default to both
            wants_reset = True
            wants_exposed = True
        
        # Prepare targeted data context
        data_context = _prepare_filtered_data_context(source, wants_reset, wants_exposed)
        
        # Build specific prompt based on query intent
        if wants_count and wants_reset:
            task_desc = f"Count the number of users needing password reset{' from ' + source if source else ''}"
        elif wants_list and wants_reset:
            task_desc = f"List the users needing password reset{' from ' + source if source else ''}"
        elif wants_count and wants_exposed:
            task_desc = f"Count the number of recently exposed users{' from ' + source if source else ''}"
        elif wants_list and wants_exposed:
            task_desc = f"List the recently exposed users{' from ' + source if source else ''}"
        else:
            task_desc = "Analyze the data based on the question asked"
        
        prompt = f"""Answer this question ONLY based on the provided data:
        
Data:
{data_context}

Question: {user_query}

Task: {task_desc}

Be concise and factual. Provide only numbers for counts, or formatted lists for records."""
        
        response = analysis_chain.invoke({
            "data": prompt,
            "query": user_query
        })
        
        return _local_format(response.strip())
    except Exception as e:
        return f"Error processing query: {str(e)}"


def handle_query(user_query: str):
    # First, try predefined intents
    predefined_intent = resolve_predefined_intent(user_query)
    if predefined_intent:
        return _execute_intent(predefined_intent)

    # Try LLM intent classification
    try:
        intent = intent_chain.invoke({"query": user_query}).strip()
    except Exception:
        intent = "UNKNOWN"

    # If a known intent was classified, execute it
    if intent != "UNKNOWN":
        raw = _get_raw_output_for_intent(intent)
        if raw is not None:
            return _safe_format(None, raw)

    # For UNKNOWN or unhandled intents, use smart generic query handling
    return _handle_generic_query(user_query)


def run_daily_report(task_names=None):
    # Ensure only a single task key is used for daily reports
    if task_names is None:
        selected = [DEFAULT_DAILY_TASKS[0]]
    elif isinstance(task_names, list):
        selected = [task_names[0]]
    else:
        selected = [task_names]

    report = {}

    for task_name in selected:
        intent = resolve_predefined_intent(task_name)
        if not intent:
            report[task_name] = "Unsupported predefined task."
            continue
        report[task_name] = _execute_intent(intent, task_name)

    return report


def precompute_format_cache(task_keys: Optional[List[str]] = None) -> dict:
    """Use the LLM formatter to build a cache for the selected task keys.

    Run this when you have quota/API access. Saves results to `Data/format_cache.json`.
    Returns the cache mapping.
    """
    selected = task_keys or DEFAULT_DAILY_TASKS
    cache = _load_format_cache()
    updated = False

    for key in selected:
        intent = resolve_predefined_intent(key)
        if not intent:
            continue
        raw = _get_raw_output_for_intent(intent)
        if raw is None:
            continue
        try:
            formatted = formatter_chain.invoke({"data": raw})
            cache[key] = formatted
            updated = True
        except Exception as e:
            print(f"Failed to format {key}: {e}")

    if updated:
        _save_format_cache(cache)

    return cache


# Example
if __name__ == "__main__":
    print(get_daily_prompt_template())
    print("\nDaily report output:\n")
    for task, response in run_daily_report().items():
        print(f"[{task}] {response}")

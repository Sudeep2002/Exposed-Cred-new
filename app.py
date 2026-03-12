import json
import os
from typing import Optional
import pandas as pd

from Chains.intent_classifier import intent_chain, analysis_chain
from Chains.response_formatter import formatter_chain
from Backend.loader import load_current_batch, load_master_data
from Backend.rules import (
    calculate_password_reset_candidates,
    get_exposure_breakdown_by_source,
    get_password_reset_count,
    get_recently_exposed_users,
)

DATA_DIR = "Data"
CACHE_PATH = os.path.join(DATA_DIR, "format_cache.json")

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
    return f"--- Report ---\n{text.strip()}\n--- End ---"

def get_raw_output_for_intent(intent: str, current_df: pd.DataFrame, master_df: pd.DataFrame) -> Optional[str]:
    if intent == "RESET_COUNT":
        return f"Users needing password reset: {get_password_reset_count(current_df, master_df)}"
    if intent == "RESET_LIST":
        return calculate_password_reset_candidates(current_df, master_df).to_string(index=False)
    if intent == "RECENT_EXPOSED_COUNT":
        df = get_recently_exposed_users(current_df, master_df)
        return f"Recently exposed users count: {len(df)}"
    if intent == "RECENT_EXPOSED_LIST":
        return get_recently_exposed_users(current_df, master_df).to_string(index=False)
    if intent == "SOURCE_BREAKDOWN":
        df = get_recently_exposed_users(current_df, master_df)
        return str(get_exposure_breakdown_by_source(df))
    return None

def handle_generic_query(user_query: str, current_df: pd.DataFrame, master_df: pd.DataFrame) -> str:
    """Smart analysis combining keyword intent filtering and LLM generation."""
    query_lower = user_query.lower()
    
    # 1. Extract intents
    wants_count = any(k in query_lower for k in ["how many", "count", "total", "number of"])
    wants_reset = any(k in query_lower for k in ["reset", "password"])
    wants_exposed = any(k in query_lower for k in ["exposed", "recent", "exposure"])
    
    # Defaults
    if wants_reset and not wants_exposed: wants_exposed = False
    elif wants_exposed and not wants_reset: wants_reset = False
    else: wants_reset = wants_exposed = True

    # 2. Extract sources
    sources = set(current_df["source"].unique()) | set(master_df["source"].unique())
    source = next((s for s in sources if s.upper() in user_query.upper()), None)

    # 3. Filter data
    filtered_curr = current_df[current_df["source"] == source] if source else current_df
    filtered_mast = master_df[master_df["source"] == source] if source else master_df

    # 4. Build Context
    context = [f"Current batch: {len(filtered_curr)} records", f"Master data: {len(filtered_mast)} records"]
    
    if wants_reset:
        resets = calculate_password_reset_candidates(filtered_curr, filtered_mast)
        context.append(f"\nReset Candidates ({len(resets)}):\n{resets[['email']].head(20).to_string(index=False)}")
    if wants_exposed:
        exposed = get_recently_exposed_users(filtered_curr, filtered_mast)
        context.append(f"\nRecently Exposed ({len(exposed)}):\n{exposed[['email', 'source']].head(20).to_string(index=False)}")

    prompt = f"Answer this question ONLY based on the provided data:\nData:\n{chr(10).join(context)}\n\nQuestion: {user_query}\n\nBe concise and factual."
    
    try:
        return analysis_chain.invoke({"data": prompt, "query": user_query}).strip()
    except Exception as e:
        return f"Error processing query: {str(e)}"

def process_query(user_query: str, current_df: pd.DataFrame, master_df: pd.DataFrame, use_llm_formatter: bool = False, task_name: str = None) -> str:
    """Core function to route query execution based dynamically on the user's prompt."""
    try:
        intent_out = intent_chain.invoke({"query": user_query}).strip().upper()
        valid_intents = {"RESET_COUNT", "RESET_LIST", "RECENT_EXPOSED_COUNT", "RECENT_EXPOSED_LIST", "SOURCE_BREAKDOWN"}
        intent = next((t for t in valid_intents if t in intent_out), "UNKNOWN")
    except Exception:
        intent = "UNKNOWN"

    if intent != "UNKNOWN":
        raw = get_raw_output_for_intent(intent, current_df, master_df)
        if raw is not None:
            if use_llm_formatter:
                try:
                    return formatter_chain.invoke({"data": raw, "query": user_query})
                except Exception:
                    return raw
            
            cache = _load_format_cache()
            if task_name and task_name in cache: return cache[task_name]
            return _local_format(raw)

    return handle_generic_query(user_query, current_df, master_df)

if __name__ == "__main__":
    print("Core App Engine Loaded.")
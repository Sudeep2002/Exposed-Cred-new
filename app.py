import json
import os
import pandas as pd

# We drop intent_chain and formatter_chain entirely! Only use analysis_chain.
from Chains.intent_classifier import analysis_chain
from Backend.rules import calculate_password_reset_candidates

DATA_DIR = "Data"
CACHE_PATH = os.path.join(DATA_DIR, "format_cache.json")

def process_query(user_query: str, current_df: pd.DataFrame, master_df: pd.DataFrame, **kwargs) -> str:
    """
    Pure dynamic context generation engine. 
    No rigid intents - we just calculate the exact math and let the LLM answer.
    """
    
    # 1. Detect and Filter by Source
    sources = set(current_df["source"].dropna().unique()) | set(master_df["source"].dropna().unique())
    sorted_sources = sorted([str(s) for s in sources if str(s).strip()], key=len, reverse=True)
    
    detected_source = None
    for s in sorted_sources:
        # Simple check if the source name appears in the user's query
        if s.lower() in user_query.lower():
            detected_source = s
            break
            
    filtered_curr = current_df
    filtered_mast = master_df
    
    if detected_source:
        # Apply strict filter to dataframes
        filtered_curr = current_df[current_df["source"].astype(str).str.lower() == detected_source.lower()]
        filtered_mast = master_df[master_df["source"].astype(str).str.lower() == detected_source.lower()]

    # 2. Pre-calculate EXACT statistics
    resets_df = calculate_password_reset_candidates(filtered_curr, filtered_mast)
    reset_count = len(resets_df)
    reset_emails = resets_df["email"].tolist() if reset_count > 0 else []
    
    curr_breakdown = filtered_curr["source"].value_counts().to_dict()
    mast_breakdown = filtered_mast["source"].value_counts().to_dict()

    # 3. Build a strict, undeniable context payload for the LLM
    context = []
    if detected_source:
        context.append(f"FILTER APPLIED: Showing data ONLY for source '{detected_source}'")
    else:
        context.append("FILTER: None (Showing all data)")
        
    context.append(f"\n--- CURRENT BATCH STATS ---")
    context.append(f"Total Exposures in Current Batch: {len(filtered_curr)}")
    context.append(f"Current Batch Source Breakdown: {curr_breakdown}")
    context.append(f"Password Resets Needed (Current users NOT in recent master data): {reset_count}")
    
    if reset_count > 0:
        context.append(f"Reset Emails (first 30): {', '.join(reset_emails[:30])}")
        
    context.append(f"\n--- MASTER DATA STATS ---")
    context.append(f"Total Historical Exposures: {len(filtered_mast)}")
    context.append(f"Historical Source Breakdown: {mast_breakdown}")

    prompt_data = "\n".join(context)
    
    # 4. Ask the LLM to answer using ONLY this context
    try:
        return analysis_chain.invoke({"data": prompt_data, "query": user_query}).strip()
    except Exception as e:
        return f"Error analyzing data: {str(e)}"

if __name__ == "__main__":
    print("Dynamic App Engine Loaded.")
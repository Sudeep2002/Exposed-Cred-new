import streamlit as st
import pandas as pd
from io import BytesIO
import re
from typing import Tuple, Optional

from Chains.intent_classifier import intent_chain, analysis_chain
from Chains.response_formatter import formatter_chain
from Backend.loader import load_current_batch, load_master_data
from Backend.predefined_tasks import resolve_predefined_intent, PREDEFINED_TASKS
from Backend.rules import (
    calculate_password_reset_candidates,
    get_password_reset_count,
    get_recently_exposed_users,
    get_exposure_breakdown_by_source,
)

# Page config
st.set_page_config(page_title="Exposed Credential Analysis", layout="wide")

# Session state for chat history and data
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "current_df" not in st.session_state:
    st.session_state.current_df = None
if "master_df" not in st.session_state:
    st.session_state.master_df = None
if "uploaded_files" not in st.session_state:
    st.session_state.uploaded_files = False

st.title("Exposed Credential Analysis Chat")
st.markdown("---")

VALID_INTENTS = {
    "RESET_COUNT",
    "RESET_LIST",
    "RECENT_EXPOSED_COUNT",
    "RECENT_EXPOSED_LIST",
    "SOURCE_BREAKDOWN",
}


def _sanitize_intent(raw_intent: str) -> str:
    """Return a known intent token from model output when possible."""
    cleaned = raw_intent.strip().upper()
    if cleaned in VALID_INTENTS:
        return cleaned
    for token in VALID_INTENTS:
        if token in cleaned:
            return token
    return "UNKNOWN"


def _show_reset_download_button() -> None:
    """Render reset-candidates download button when data is available."""
    df_reset = calculate_password_reset_candidates(
        st.session_state.current_df,
        st.session_state.master_df,
    )
    if df_reset.empty:
        return

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_reset.to_excel(writer, index=False)
    output.seek(0)

    st.download_button(
        label="Download Password Reset Candidates",
        data=output.getvalue(),
        file_name="password_reset_candidates.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def _append_chat_message(role: str, content: str) -> None:
    st.session_state.chat_history.append({"role": role, "content": content})


def _extract_source_from_query(query: str) -> Optional[str]:
    """Extract source name from query (e.g., 'BK', 'SSC', 'XMC', etc.)."""
    query_upper = query.upper()
    
    # Get all unique sources from data
    sources = set(st.session_state.current_df["source"].unique()) | set(st.session_state.master_df["source"].unique())
    
    # Check for exact source matches
    for source in sources:
        if source.upper() in query_upper:
            return source
    
    # Check for common abbreviations
    abbreviations = {
        "BK": "BK",
        "SSC": "SSC",
        "XMC": "XMC",
    }
    
    for abbr, full_name in abbreviations.items():
        if abbr in query_upper:
            return full_name
    
    return None


def _extract_intent_keywords(query: str) -> Tuple[bool, bool, bool, bool]:
    """Extract intent from query.
    Returns (wants_count, wants_list, wants_reset, wants_exposed)"""
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


def _prepare_filtered_data_context(source: Optional[str], wants_reset: bool, wants_exposed: bool) -> str:
    """Prepare targeted data context based on extracted intent."""
    
    # Filter data by source if specified
    if source:
        filtered_current = st.session_state.current_df[st.session_state.current_df["source"] == source]
        filtered_master = st.session_state.master_df[st.session_state.master_df["source"] == source]
    else:
        filtered_current = st.session_state.current_df
        filtered_master = st.session_state.master_df
    
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


def _execute_intent(user_query: str) -> str:
    """Execute user query and return formatted response."""

    predefined_intent = resolve_predefined_intent(user_query)
    if predefined_intent:
        intent = predefined_intent
    else:
        try:
            model_output = intent_chain.invoke({"query": user_query})
            intent = _sanitize_intent(model_output)
        except Exception as e:
            return f"I could not classify that query right now. Details: {e}"

    if intent == "RESET_COUNT":
        result = get_password_reset_count(
            st.session_state.current_df,
            st.session_state.master_df,
        )
        text = f"Users needing password reset: {result}"

    elif intent == "RESET_LIST":
        df = calculate_password_reset_candidates(
            st.session_state.current_df,
            st.session_state.master_df,
        )
        text = df.to_string(index=False)

    elif intent == "RECENT_EXPOSED_COUNT":
        df = get_recently_exposed_users(
            st.session_state.current_df,
            st.session_state.master_df,
        )
        text = f"Recently exposed users count: {len(df)}"

    elif intent == "RECENT_EXPOSED_LIST":
        df = get_recently_exposed_users(
            st.session_state.current_df,
            st.session_state.master_df,
        )
        text = df.to_string(index=False)

    elif intent == "SOURCE_BREAKDOWN":
        df = get_recently_exposed_users(
            st.session_state.current_df,
            st.session_state.master_df,
        )
        breakdown = get_exposure_breakdown_by_source(df)
        text = str(breakdown)

    else:
        # For UNKNOWN intents, use smart generic analysis
        return _handle_generic_query(user_query)

    try:
        formatted = formatter_chain.invoke({"data": text})
        return formatted
    except Exception:
        return text


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
        else:
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
        
        return response.strip()
    except Exception as e:
        return f"Error processing query: {str(e)}"


# Sidebar for file uploads
with st.sidebar:
    st.header("Upload Data Files")

    current_batch_file = st.file_uploader(
        "Upload Current Batch Excel Sheet",
        type=["xlsx", "xls"],
        key="current_batch",
    )

    master_data_file = st.file_uploader(
        "Upload Master Data Excel Sheet",
        type=["xlsx", "xls"],
        key="master_data",
    )

    if current_batch_file and master_data_file:
        current_path = "temp_current_batch.xlsx"
        master_path = "temp_master_data.xlsx"

        with open(current_path, "wb") as f:
            f.write(current_batch_file.getbuffer())
        with open(master_path, "wb") as f:
            f.write(master_data_file.getbuffer())

        try:
            st.session_state.current_df = load_current_batch(current_path)
            st.session_state.master_df = load_master_data(master_path)
            st.session_state.uploaded_files = True
            st.sidebar.success("Files loaded successfully!")
        except Exception as e:
            st.sidebar.error(f"Error loading files: {e}")


def _handle_query(user_query: str, allow_reset_download: bool) -> None:
    _append_chat_message("user", user_query)
    with st.spinner("Analyzing..."):
        response = _execute_intent(user_query)
    _append_chat_message("assistant", response)

    if allow_reset_download and "reset" in user_query.lower():
        st.markdown("---")
        _show_reset_download_button()


# Main chat interface
if not st.session_state.uploaded_files:
    st.info("Please upload both Excel sheets in the sidebar to get started.")
else:
    st.success("Data files loaded. You can now ask questions!")

    st.markdown("**Quick questions you can ask:**")
    cols = st.columns(3)
    for i, (key, meta) in enumerate(PREDEFINED_TASKS.items()):
        col = cols[i % 3]
        if col.button(meta["prompt"]):
            _handle_query(meta["prompt"], allow_reset_download=("reset" in key))

    chat_history_container = st.container()

    user_query = st.chat_input("Ask a question about the exposed credentials...")
    if user_query:
        _handle_query(user_query, allow_reset_download=True)

    with chat_history_container:
        for message in st.session_state.chat_history:
            st.chat_message(message["role"]).write(message["content"])


if st.session_state.uploaded_files and st.sidebar.button("Clear Chat History"):
    st.session_state.chat_history = []
    st.rerun()

import streamlit as st
import pandas as pd
from io import BytesIO

from app import process_query  # Directly use the unified core logic
from Backend.loader import load_current_batch, load_master_data
from Backend.predefined_tasks import PREDEFINED_TASKS
from Backend.rules import calculate_password_reset_candidates

st.set_page_config(page_title="Exposed Credential Analysis", layout="wide")

# Initialize Session State
for key in ["chat_history", "current_df", "master_df"]:
    if key not in st.session_state:
        st.session_state[key] = [] if key == "chat_history" else None
if "uploaded_files" not in st.session_state:
    st.session_state.uploaded_files = False

st.title("Exposed Credential Analysis Chat")
st.markdown("---")

def _show_reset_download_button() -> None:
    df_reset = calculate_password_reset_candidates(st.session_state.current_df, st.session_state.master_df)
    if df_reset.empty: return

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

def _handle_query(user_query: str, allow_reset_download: bool) -> None:
    st.session_state.chat_history.append({"role": "user", "content": user_query})
    
    with st.spinner("Analyzing..."):
        # Centralized engine handles intent parsing, LLM calls, and rule execution
        response = process_query(
            user_query, 
            st.session_state.current_df, 
            st.session_state.master_df, 
            use_llm_formatter=True
        )
        
    st.session_state.chat_history.append({"role": "assistant", "content": response})

    if allow_reset_download and "reset" in user_query.lower():
        st.markdown("---")
        _show_reset_download_button()

# Sidebar Setup
with st.sidebar:
    st.header("Upload Data Files")
    current_batch_file = st.file_uploader("Upload Current Batch Excel", type=["xlsx", "xls"])
    master_data_file = st.file_uploader("Upload Master Data Excel", type=["xlsx", "xls"])

    if current_batch_file and master_data_file:
        try:
            st.session_state.current_df = load_current_batch(BytesIO(current_batch_file.getvalue()))
            st.session_state.master_df = load_master_data(BytesIO(master_data_file.getvalue()))
            st.session_state.uploaded_files = True
            st.success("Files loaded successfully!")
        except Exception as e:
            st.error(f"Error loading files: {e}")

# Main Interface
if not st.session_state.uploaded_files:
    st.info("Please upload both Excel sheets in the sidebar to get started.")
else:
    st.success("Data files loaded. You can now ask questions!")
    
    st.markdown("**Quick questions you can ask:**")
    cols = st.columns(3)
    for i, (key, meta) in enumerate(PREDEFINED_TASKS.items()):
        if cols[i % 3].button(meta["prompt"]):
            _handle_query(meta["prompt"], allow_reset_download=("reset" in key))

    user_query = st.chat_input("Ask a question about the exposed credentials...")
    if user_query:
        _handle_query(user_query, allow_reset_download=True)

    for message in st.session_state.chat_history:
        st.chat_message(message["role"]).write(message["content"])

if st.session_state.uploaded_files and st.sidebar.button("Clear Chat History"):
    st.session_state.chat_history = []
    st.rerun()
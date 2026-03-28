import streamlit as st
import pandas as pd
from io import BytesIO

from app import process_query  
from Backend.loader import load_current_batch, load_master_data
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
    """Generates an Excel file of users who need a password reset."""
    curr_df = st.session_state.current_df.copy()
    mast_df = st.session_state.master_df.copy()
    
    # Clean emails for accurate math
    curr_emails = curr_df['email'].astype(str).str.lower().str.strip()
    mast_emails = mast_df['email'].astype(str).str.lower().str.strip()
    
    # Find Resets (In current, NOT in master)
    resets_df = curr_df[~curr_emails.isin(mast_emails)]
    
    if resets_df.empty: 
        return

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        resets_df.to_excel(writer, index=False)
    output.seek(0)

    st.download_button(
        label="📥 Download Password Resets (New Exposures)",
        data=output.getvalue(),
        file_name="password_resets.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

def _show_repeated_download_button() -> None:
    """Generates an Excel file analyzing repeated users across all time."""
    curr_df = st.session_state.current_df.copy()
    mast_df = st.session_state.master_df.copy()
    
    # Clean emails
    curr_df['email_clean'] = curr_df['email'].astype(str).str.lower().str.strip()
    mast_df['email_clean'] = mast_df['email'].astype(str).str.lower().str.strip()
    
    # Find Repeated (In BOTH current and master)
    repeated_emails = curr_df['email_clean'][curr_df['email_clean'].isin(mast_df['email_clean'])].unique()
    
    if len(repeated_emails) == 0:
        return
        
    # Combine their history from both sheets
    curr_repeats = curr_df[curr_df['email_clean'].isin(repeated_emails)]
    mast_repeats = mast_df[mast_df['email_clean'].isin(repeated_emails)]
    combined = pd.concat([curr_repeats, mast_repeats])
    
    # Group by email to create the analysis report
    analysis = combined.groupby('email').agg(
        total_appearances=('email', 'count'),
        sources=('source', lambda x: ", ".join(x.dropna().astype(str).unique())),
        dates=('exposure_date', lambda x: ", ".join(x.dropna().astype(str).unique()))
    ).reset_index()

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        analysis.to_excel(writer, index=False)
    output.seek(0)

    st.download_button(
        label="📥 Download Repeated User Analysis",
        data=output.getvalue(),
        file_name="repeated_user_analysis.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

def _handle_query(user_query: str) -> None:
    st.session_state.chat_history.append({"role": "user", "content": user_query})
    
    with st.spinner("Analyzing data..."):
        response = process_query(
            user_query, 
            st.session_state.current_df, 
            st.session_state.master_df
        )
        
    st.session_state.chat_history.append({"role": "assistant", "content": response})

    # Dynamically show the right button based on what the user asked!
    query_lower = user_query.lower()
    
    if any(word in query_lower for word in ["reset", "new exposure", "not in master"]):
        st.markdown("---")
        _show_reset_download_button()
        
    if any(word in query_lower for word in ["repeat", "reappear", "history", "analyze"]):
        st.markdown("---")
        _show_repeated_download_button()

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
    
    user_query = st.chat_input("Ask a question about the current batch...")
    if user_query:
        _handle_query(user_query)

    for message in st.session_state.chat_history:
        st.chat_message(message["role"]).write(message["content"])

if st.session_state.uploaded_files and st.sidebar.button("Clear Chat History"):
    st.session_state.chat_history = []
    st.rerun()
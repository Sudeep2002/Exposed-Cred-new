import streamlit as st
import pandas as pd
from io import BytesIO
from app import process_query  # This connects to the app.py file we just built!

# --- 1. PAGE SETUP ---
st.set_page_config(page_title="SOC Credential Triage", layout="wide")
st.title("🛡️ Enterprise SOC AI Assistant")

# --- 2. SESSION STATE (Memory) ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [{"role": "assistant", "content": "Hello! Please upload your incoming and master datasets, then ask me anything."}]
if "current_df" not in st.session_state:
    st.session_state.current_df = None
if "master_df" not in st.session_state:
    st.session_state.master_df = None

# --- 3. FILE UPLOAD SECTION ---
st.markdown("### 📁 Upload Data")
col1, col2 = st.columns(2)

with col1:
    incoming_files = st.file_uploader("Upload Incoming Source Files (BK, SSC, etc.)", type=["xlsx", "csv"], accept_multiple_files=True)

with col2:
    master_file = st.file_uploader("Upload Master Data File", type=["xlsx", "csv"])

# --- 4. PROCESSING THE FILES ---
if incoming_files and master_file:
    with st.spinner("Loading and merging data..."):
        # Load the Master File
        if master_file.name.endswith('.csv'):
            st.session_state.master_df = pd.read_csv(master_file)
        else:
            st.session_state.master_df = pd.read_excel(master_file, engine='openpyxl')

        # Combine all Incoming Files safely
        incoming_dfs = []
        for file in incoming_files:
            if file.name.endswith('.csv'):
                incoming_dfs.append(pd.read_csv(file))
            else:
                incoming_dfs.append(pd.read_excel(file, engine='openpyxl'))
                
        # Stack them together
        st.session_state.current_df = pd.concat(incoming_dfs, ignore_index=True)
    
    st.success("✅ Files successfully loaded! The AI is ready for your questions.")

# --- 5. CHAT LOGIC ---
def _handle_query(user_query: str):
    # Add user message to history
    st.session_state.chat_history.append({"role": "user", "content": user_query})
    
    # Run the Smart AI Router from app.py
    with st.spinner("Analyzing data based on SOC policies..."):
        response = process_query(
            user_query, 
            st.session_state.current_df, 
            st.session_state.master_df
        )
        
    # Add AI response to history
    st.session_state.chat_history.append({"role": "assistant", "content": response})

# --- 6. CHAT INTERFACE ---
st.markdown("---")

# Draw the chat history
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# The Chat Input Box
if user_query := st.chat_input("E.g., 'Who needs a password reset?' or 'Analyze repeated users'"):
    if st.session_state.current_df is None or st.session_state.master_df is None:
        st.error("⚠️ Please upload both the Incoming Data and Master Data files first.")
    else:
        # Display the user's message instantly
        with st.chat_message("user"):
            st.markdown(user_query)
        # Process the answer
        _handle_query(user_query)
        # Rerun to update the UI
        st.rerun()
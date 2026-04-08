import pandas as pd
import re
from datetime import datetime
from langchain_ollama import OllamaLLM
from langchain_experimental.agents.agent_toolkits import create_pandas_dataframe_agent

def process_query(user_query: str, current_df: pd.DataFrame, master_df: pd.DataFrame, **kwargs) -> str:
    """
    Hybrid Router: Enterprise SOC Cooldown Policy (With Data Normalization)
    """
    query_lower = user_query.lower()

    # ==========================================
    # 🧹 1. DATA NORMALIZATION (The Fix!)
    # ==========================================
    # Always work on copies so we don't accidentally corrupt the Streamlit session state
    curr_df = current_df.copy()
    mast_df = master_df.copy()

    # Lowercase all column names to ignore capitalization (e.g., 'User' becomes 'user')
    curr_df.columns = curr_df.columns.str.lower()
    mast_df.columns = mast_df.columns.str.lower()

    # Map incoming variations to our internal standard names
    col_mapper = {
        'user': 'email',
        'email address': 'email',
        'date': 'exposure_date',
        'reset_status': 'reset'
    }
    curr_df.rename(columns=col_mapper, inplace=True)
    mast_df.rename(columns=col_mapper, inplace=True)

    # Ensure the 'reset' column exists in master data (fallback if missing)
    if 'reset' not in mast_df.columns:
        mast_df['reset'] = 'NA'

    # Clean strings and parse dates safely
    curr_df['email_clean'] = curr_df['email'].astype(str).str.lower().str.strip()
    mast_df['email_clean'] = mast_df['email'].astype(str).str.lower().str.strip()
    
    curr_df['parsed_date'] = pd.to_datetime(curr_df['exposure_date'], errors='coerce')
    mast_df['parsed_date'] = pd.to_datetime(mast_df['exposure_date'], errors='coerce')

    # ==========================================
    # 🚥 2. THE ROUTER: Categorize the Question
    # ==========================================
    
    email_matches = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', query_lower)
    
    known_vendors = ["bk", "ssc", "bitsight", "xmc", "xm"]
    detected_vendor = next((v for v in known_vendors if v in query_lower), None)
    
    complex_keywords = ["%", "percent", "most", "least", "compare"]
    is_complex = any(word in query_lower for word in complex_keywords)

    is_asking_reset = any(word in query_lower for word in ["reset", "new exposure", "action", "valid"])
    is_asking_analysis = any(word in query_lower for word in ["repeat", "history", "analyze", "safe"])
    is_asking_summary = any(word in query_lower for word in ["total", "summary", "how many users"])

    # ==========================================
    # ⚡ 3. THE FAST LANE (Instant Pandas Math)
    # ==========================================
    
    # CATEGORY 1: The 6-Month Reset Logic (Enterprise Policy)
    if not is_complex and is_asking_reset:
        print("🚥 ROUTER: Running 6-Month Cooldown Policy...")
        
        resets_needed = []
        today = pd.Timestamp.now()
        six_months_ago = today - pd.DateOffset(months=6)

        for _, row in curr_df.iterrows():
            email = row['email_clean']
            user_hist = mast_df[mast_df['email_clean'] == email]

            if user_hist.empty:
                resets_needed.append(row['email'])
            else:
                dones = user_hist[user_hist['reset'].astype(str).str.lower() == 'done']
                
                if not dones.empty:
                    last_action_date = dones['parsed_date'].max()
                else:
                    last_action_date = user_hist['parsed_date'].min()
                
                if pd.notna(last_action_date) and last_action_date <= six_months_ago:
                    resets_needed.append(row['email'])
        
        resets_df = curr_df[curr_df['email'].isin(resets_needed)]
        
        if detected_vendor:
            resets_df = resets_df[resets_df['source'].astype(str).str.lower().str.strip() == detected_vendor]
            
        count = len(resets_df)
        vendor_text = f" from {detected_vendor.upper()}" if detected_vendor else ""
        
        if any(w in query_lower for w in ["who", "list", "show"]):
            emails = "\n- ".join(resets_df['email'].tolist())
            return f"🚨 **ACTION REQUIRED:** Found {count} valid users{vendor_text} who require a password reset:\n- {emails}"
        return f"🚨 **ACTION REQUIRED:** There are {count} valid users{vendor_text} who require a password reset."

    # CATEGORY 4: Single User Profile Lookup
    if email_matches and not is_complex:
        print("🚥 ROUTER: Looking up specific user profile...")
        target_email = email_matches[0]
        in_curr = target_email in curr_df['email_clean'].values
        user_hist = mast_df[mast_df['email_clean'] == target_email]
        
        if not in_curr and user_hist.empty:
            return f"✅ **NOT FOUND:** `{target_email}` is completely clean."
            
        response = f"🔍 **Profile for `{target_email}`:**\n"
        response += f"- **In Current Batch?** {'Yes ⚠️' if in_curr else 'No ✅'}\n"
        
        if not user_hist.empty:
            total_occurrences = len(user_hist)
            dones = user_hist[user_hist['reset'].astype(str).str.lower() == 'done']
            last_reset = dones['parsed_date'].max().strftime('%Y-%m-%d') if not dones.empty else "NEVER"
            sources = ", ".join(user_hist['source'].dropna().astype(str).unique())
            
            response += f"- **Historical Exposures:** {total_occurrences} times (Sources: {sources})\n"
            response += f"- **Last Reset 'Done':** {last_reset}\n"
        else:
            response += "- **Historical Exposures:** 0 (Brand New)\n"
            
        return response

    # ==========================================
    # 🧠 4. THE SMART LANE (Autonomous Agent)
    # ==========================================
    print("🚥 ROUTER: Taking the Smart Lane (AI Agent)...")
    
    llm = OllamaLLM(model="llama3.2", temperature=0, client_kwargs={"timeout": 120})

    # Update system prefix so the Agent knows our standardized column names
    system_prefix = """
    You are an elite Security Data Analyst managing exposed employee credentials. 
    You have access to two pandas DataFrames:
    - df1: The 'current batch' of recent exposures (Columns: email, exposure_date, source)
    - df2: The 'master data' of historical exposures (Columns: email, exposure_date, source, reset)

    COMPANY BUSINESS DEFINITIONS:
    1. "Password Reset / Valid User": Determined by a 6-month policy. If they are new, OR their last Reset='Done' date is > 6 months ago, they are Valid for a reset.
    2. "Cooldown / Safe": User exists in master data and their last Reset='Done' was < 6 months ago.

    CRITICAL PANDAS RULES (DO NOT FAIL THESE):
    1. NEVER compare two columns directly with `==`. 
    2. ALWAYS use `.isin()` to find matches.
    3. To run pandas code, use the exact format below:
    
    Thought: [Explain your plan]
    Action: python_repl_ast
    Action Input: [Your exact pandas code here]
    
    FINAL OUTPUT RULES:
    - Provide exact numbers, percentages, or summaries clearly. Do not output raw python code.
    """

    agent = create_pandas_dataframe_agent(llm, [curr_df, mast_df], verbose=True, allow_dangerous_code=True, prefix=system_prefix, max_iterations=15, handle_parsing_errors=True)

    try:
        return agent.invoke({"input": user_query})["output"]
    except Exception as e:
        print(f"\n[SECURE LOG] Agent Error: {str(e)}\n") 
        return "I encountered an internal issue analyzing that specific request. Please try rephrasing."
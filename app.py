import pandas as pd
import re
from langchain_ollama import OllamaLLM
from langchain_experimental.agents.agent_toolkits import create_pandas_dataframe_agent

def process_query(user_query: str, current_df: pd.DataFrame, master_df: pd.DataFrame, **kwargs) -> str:
    """
    Hybrid Router: Enterprise SOC Cooldown Policy (Final Production Version)
    """
    query_lower = user_query.lower()

    # ==========================================
    # 🧹 1. DATA NORMALIZATION & CLEANUP
    # ==========================================
    # Always work on copies so we don't accidentally corrupt the Streamlit session state
    curr_df = current_df.copy()
    mast_df = master_df.copy()

    # Lowercase and strip columns to prevent KeyError
    curr_df.columns = curr_df.columns.str.lower().str.strip()
    mast_df.columns = mast_df.columns.str.lower().str.strip()

    # Map incoming variations to our internal standard names
    col_mapper = {
        'user': 'email',
        'email address': 'email',
        'date': 'exposure_date',
        'reset_status': 'reset'
    }
    curr_df.rename(columns=col_mapper, inplace=True)
    mast_df.rename(columns=col_mapper, inplace=True)

    # Automatically filter by Valid_User if the column exists in incoming data
    if 'valid_user' in curr_df.columns:
        curr_df = curr_df[curr_df['valid_user'].astype(str).str.lower().str.strip() == 'true']

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
    
    # Notice: Vendors and "summary/total" are NOT in the complex list
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
        print("🚥 ROUTER: Running Hardened 6-Month Cooldown Policy...")
        
        resets_needed = []

        for _, row in curr_df.iterrows():
            email = row['email_clean']
            user_hist = mast_df[mast_df['email_clean'] == email]
            
            # Calculate exactly 6 months prior to THIS specific exposure
            incoming_date = row['parsed_date']
            if pd.isna(incoming_date):
                incoming_date = pd.Timestamp.now() # Fallback if date is missing
            cutoff_date = incoming_date - pd.DateOffset(months=6)

            if user_hist.empty:
                # Brand new user
                resets_needed.append(row['email'])
            else:
                # Strip whitespace to safely catch 'Done '
                dones = user_hist[user_hist['reset'].astype(str).str.lower().str.strip() == 'done']
                
                if not dones.empty:
                    last_action_date = dones['parsed_date'].max()
                else:
                    last_action_date = user_hist['parsed_date'].min()
                
                if pd.notna(last_action_date) and last_action_date <= cutoff_date:
                    resets_needed.append(row['email'])
        
        # Deduplicate the final list so the count is mathematically perfect
        resets_df = curr_df[curr_df['email'].isin(resets_needed)].drop_duplicates(subset=['email_clean'])
        
        if detected_vendor:
            resets_df = resets_df[resets_df['source'].astype(str).str.lower().str.strip() == detected_vendor]
            
        count = len(resets_df)
        vendor_text = f" from {detected_vendor.upper()}" if detected_vendor else ""
        
        if any(w in query_lower for w in ["who", "list", "show"]):
            emails = "\n- ".join(resets_df['email'].tolist())
            return f"🚨 **ACTION REQUIRED:** Found {count} unique, valid users{vendor_text} who require a password reset:\n- {emails}"
        return f"🚨 **ACTION REQUIRED:** There are {count} unique, valid users{vendor_text} who require a password reset."

    # CATEGORY 2: The Repeated Analysis Logic
    if not is_complex and is_asking_analysis:
        print("🚥 ROUTER: Running Repeated Analysis...")
        
        # 🚀 THE FIX: Use Python sets instead of Pandas .isin() to bypass the 2D Buffer error
        curr_emails = set(curr_df['email_clean'].dropna().tolist())
        mast_emails = set(mast_df['email_clean'].dropna().tolist())
        
        # Find the intersection (emails that exist in both sets)
        repeated_emails = list(curr_emails.intersection(mast_emails))
        count = len(repeated_emails)
        
        vendor_text = f" from {detected_vendor.upper()}" if detected_vendor else ""
        
        if count == 0:
            return f"There are no repeated users{vendor_text} in this batch."
        
        if any(w in query_lower for w in ["who", "list", "analyze", "history"]):
            curr_repeats = curr_df[curr_df['email_clean'].isin(repeated_emails)]
            mast_repeats = mast_df[mast_df['email_clean'].isin(repeated_emails)]
            combined_repeats = pd.concat([curr_repeats, mast_repeats])
            
            analysis = combined_repeats.groupby('email').agg(
                total_appearances=('email', 'count'),
                sources=('source', lambda x: ", ".join(x.dropna().astype(str).unique())),
                dates=('exposure_date', lambda x: ", ".join(x.dropna().astype(str).unique()))
            ).reset_index()
            
            report_lines = [f"Found {count} repeated users{vendor_text}. Here is their historical analysis:\n"]
            for _, row in analysis.iterrows():
                report_lines.append(f"• **{row['email']}**")
                report_lines.append(f"  - Times Exposed: {row['total_appearances']}")
                report_lines.append(f"  - Found in Sources: {row['sources']}")
                report_lines.append(f"  - Dates of Exposure: {row['dates']}\n")
            
            return "\n".join(report_lines)
            
        return f"There are {count} repeated/reappearing users{vendor_text} in this batch. Ask me to 'analyze' them to see their full history."

    # CATEGORY 4: Single User Profile Lookup
    if email_matches and not is_complex:
        print("🚥 ROUTER: Looking up specific user profile...")
        target_email = email_matches[0]
        in_curr = target_email in curr_df['email_clean'].values
        user_hist = mast_df[mast_df['email_clean'] == target_email]
        
        if not in_curr and user_hist.empty:
            return f"✅ **NOT FOUND:** `{target_email}` is completely clean. Not in current batch or master."
            
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

    # CATEGORY 5: Executive Summary
    if not is_complex and is_asking_summary:
        print("🚥 ROUTER: Taking the Fast Lane (Executive Summary)...")
        total_curr = len(curr_df['email_clean'].unique())
        total_mast = len(mast_df['email_clean'].unique())
        return f"📊 **Executive Summary:** There are a total of **{total_curr} unique valid users** in the current batch, and **{total_mast} historical records** in the master database."

    # ==========================================
    # 🧠 4. THE SMART LANE (Autonomous Agent)
    # ==========================================
    print("🚥 ROUTER: Taking the Smart Lane (AI Agent)...")
    
    llm = OllamaLLM(model="llama3.2", temperature=0, client_kwargs={"timeout": 120})

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

    agent = create_pandas_dataframe_agent(
        llm, 
        [curr_df, mast_df], 
        verbose=True, 
        allow_dangerous_code=True, 
        prefix=system_prefix, 
        max_iterations=15, 
        handle_parsing_errors=True
    )

    try:
        response = agent.invoke({"input": user_query})
        return response["output"]
    except Exception as e:
        print(f"\n[SECURE LOG] Agent Error: {str(e)}\n") 
        return "I encountered an internal issue analyzing that specific request. Please try rephrasing."
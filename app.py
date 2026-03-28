import pandas as pd
import re
from langchain_ollama import OllamaLLM
from langchain_experimental.agents.agent_toolkits import create_pandas_dataframe_agent

def process_query(user_query: str, current_df: pd.DataFrame, master_df: pd.DataFrame, **kwargs) -> str:
    """
    Hybrid Router: Enterprise SOC Edition (Full Coverage)
    """
    query_lower = user_query.lower()

    # Clean emails once for all comparisons
    current_df['email_clean'] = current_df['email'].astype(str).str.lower().str.strip()
    master_df['email_clean'] = master_df['email'].astype(str).str.lower().str.strip()
    
    curr_emails = current_df['email_clean']
    mast_emails = master_df['email_clean']

    # ==========================================
    # 🚥 THE ROUTER: Categorize the Question
    # ==========================================
    
    # 1. Look for explicit email addresses in the chat
    email_matches = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', query_lower)
    
    # 2. Look for complex/analytical keywords (Send to Agent)
    complex_keywords = ["%", "percent", "most", "least", "compare", "total", "vendor", "source", "bk", "ssc", "bitsight", "xmc"]
    is_complex = any(word in query_lower for word in complex_keywords)

    # 3. Look for standard action keywords (Send to Fast Lane)
    is_asking_reset = any(word in query_lower for word in ["reset", "new exposure", "not in master", "action"])
    is_asking_analysis = any(word in query_lower for word in ["repeat", "reappear", "history", "analyze", "safe", "already known"])

    # ==========================================
    # ⚡ THE FAST LANE (Instant Pandas Math)
    # ==========================================
    
    # CATEGORY 4: Single User Lookup
    if email_matches and not is_complex:
        print("🚥 ROUTER: Taking Fast Lane (Single User Lookup)...")
        target_email = email_matches[0]
        in_curr = target_email in curr_emails.values
        in_mast = target_email in mast_emails.values
        
        if in_curr and not in_mast:
            return f"🚨 **ACTION REQUIRED:** The user `{target_email}` is a NEW exposure in the current batch and requires a password reset."
        elif in_curr and in_mast:
            history = master_df[master_df['email_clean'] == target_email]
            sources = ", ".join(history['source'].dropna().astype(str).unique())
            return f"🛡️ **SAFE / REPEATED:** The user `{target_email}` is in the current batch, but they are already known in the master database. (Previous sources: {sources})."
        elif not in_curr and in_mast:
            return f"ℹ️ **HISTORICAL ONLY:** The user `{target_email}` is NOT in the current batch, but they do exist in the historical master data."
        else:
            return f"✅ **NOT FOUND:** The user `{target_email}` was not found in any of the uploaded data."

    # CATEGORY 1 & 2: Standard Resets and Repeats
    if not is_complex and (is_asking_reset or is_asking_analysis):
        print("🚥 ROUTER: Taking the Fast Lane (Pandas Rules)...")
        
        # CATEGORY 1: The Reset Logic
        if is_asking_reset:
            resets_df = current_df[~curr_emails.isin(mast_emails)]
            count = len(resets_df)
            
            if any(w in query_lower for w in ["who", "list", "show"]):
                emails = "\n- ".join(resets_df['email'].tolist())
                return f"There are {count} users who require a password reset (New Exposures). Here is the list:\n- {emails}"
            return f"There are {count} users who require a password reset (New Exposures)."
            
        # CATEGORY 2: The Repeated Analysis Logic
        if is_asking_analysis:
            repeated_emails = curr_emails[curr_emails.isin(mast_emails)].unique()
            count = len(repeated_emails)
            
            if count == 0:
                return "There are no repeated users in this batch."
            
            if any(w in query_lower for w in ["who", "list", "analyze", "history"]):
                curr_repeats = current_df[current_df['email_clean'].isin(repeated_emails)]
                mast_repeats = master_df[master_df['email_clean'].isin(repeated_emails)]
                combined_repeats = pd.concat([curr_repeats, mast_repeats])
                
                analysis = combined_repeats.groupby('email').agg(
                    total_appearances=('email', 'count'),
                    sources=('source', lambda x: ", ".join(x.dropna().astype(str).unique())),
                    dates=('exposure_date', lambda x: ", ".join(x.dropna().astype(str).unique()))
                ).reset_index()
                
                report_lines = [f"Found {count} repeated users. Here is their historical analysis:\n"]
                for _, row in analysis.iterrows():
                    report_lines.append(f"• **{row['email']}**")
                    report_lines.append(f"  - Times Exposed: {row['total_appearances']}")
                    report_lines.append(f"  - Found in Sources: {row['sources']}")
                    report_lines.append(f"  - Dates of Exposure: {row['dates']}\n")
                
                return "\n".join(report_lines)
                
            return f"There are {count} repeated/reappearing users in this batch. Ask me to 'analyze repeated users' to see their full history."

    # ==========================================
    # 🧠 THE SMART LANE (Autonomous Agent)
    # ==========================================
    print("🚥 ROUTER: Taking the Smart Lane (AI Agent)...")
    
    # CATEGORY 3 & 5: Complex Analytics, Vendor Filtering, and Summaries
    llm = OllamaLLM(
        model="llama3.2", 
        base_url="http://localhost:11434",
        temperature=0,
        client_kwargs={"timeout": 120}
    )

    system_prefix = """
    You are an elite Security Data Analyst managing exposed employee credentials. 
    You have access to two pandas DataFrames:
    - df1: The 'current batch' of recent exposures (Columns: email, exposure_date, source)
    - df2: The 'master data' of historical exposures (Columns: email, exposure_date, source)

    COMPANY BUSINESS DEFINITIONS:
    1. "Password Reset" / "New": A user's email exists in the current batch (df1) BUT NOT in the master data (df2).
    2. "Repeated User" / "Safe": A user's email exists in BOTH the current batch (df1) AND the master data (df2).
    3. "Source": The vendor who found the leak (e.g., BK, SSC, Bitsight, XMC). 

    CRITICAL FORMATTING RULES FOR EXECUTING CODE:
    To run pandas code, you MUST use the exact format below. Do NOT use "Action: print(...)".
    
    Thought: [Explain what you are about to do]
    Action: python_repl_ast
    Action Input: [Your exact pandas code here, e.g., df1['source'].value_counts()]
    
    FINAL OUTPUT RULES:
    - Always lowercase and strip emails before comparing: df['email'].astype(str).str.lower().str.strip()
    - When filtering by a source/vendor, ensure case-insensitive string matching.
    - Provide the exact number, percentage, or summary in a clear, professional sentence based on the Observation.
    """
# ... [Keep your system_prefix exactly the same] ...

    agent = create_pandas_dataframe_agent(
        llm,
        [current_df, master_df],
        verbose=True,
        allow_dangerous_code=True,
        prefix=system_prefix,
        max_iterations=15,
        handle_parsing_errors=True  # <-- FIX 1: The AI will now self-correct bad formatting!
    )

    try:
        response = agent.invoke({"input": user_query})
        return response["output"]
    except Exception as e:
        # <-- FIX 2: Secure Error Handling (No code leakage)
        # 1. Print the raw code/error to your VS Code terminal for debugging
        print(f"\n[SECURE LOG] Agent Error: {str(e)}\n") 
        
        # 2. Return a safe, sanitized message to the end-user
        return "I encountered an internal issue analyzing that specific request. Please try rephrasing your question."
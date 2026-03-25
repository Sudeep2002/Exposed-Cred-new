import pandas as pd
from langchain_ollama import OllamaLLM
from langchain_experimental.agents.agent_toolkits import create_pandas_dataframe_agent

def process_query(user_query: str, current_df: pd.DataFrame, master_df: pd.DataFrame, **kwargs) -> str:
    """
    Autonomous Agent Engine: 
    The AI will write its own Pandas code to find the answer!
    """
    
    # 1. Initialize your local LLM (Using the faster llama3.2!)
    llm = OllamaLLM(
        model="qwen2.5-coder:7b", 
        base_url="http://localhost:11434",
        temperature=0,
        client_kwargs={"timeout": 120}
    )

    # 2. Give the agent a strict persona and instructions
    # We pass BOTH dataframes as a list: df1 is current_batch, df2 is master_data
    system_prefix = """
    You are an elite Security Data Analyst managing exposed employee credentials. 
    You have access to two pandas DataFrames:
    - df1: The 'current batch' of recent exposures (Columns: email, exposure_date, source)
    - df2: The 'master data' of all historical exposures (Columns: email, exposure_date, source)

    COMPANY BUSINESS DEFINITIONS (THE DICTIONARY):
    1. "Password Reset Needed" (or "New Exposure"): This strictly means a user's email exists in the current batch (df1) BUT DOES NOT exist in the master data (df2).
    2. "Repeated User" (or "Safe / Already Known"): This strictly means a user's email exists in BOTH the current batch (df1) AND the master data (df2).
    3. "Source": The vendor or system that discovered the exposure (e.g., 'BK', 'SSC', 'Bitsight', 'XMC').

    DATA HANDLING BEST PRACTICES:
    - When comparing emails between DataFrames, always ensure you lowercase and strip whitespace from the strings first to avoid false mismatches (e.g., df['email'].str.lower().str.strip()).
    - If filtering by a specific 'source', ensure case-insensitive matching.

    FINAL OUTPUT RULES:
    - Write and execute the exact pandas code to find the answer.
    - DO NOT output your thought process or the raw python code to the user.
    - If asked for a count, provide the exact number in a clear, professional sentence.
    - If asked for a list of users, provide the exact list of emails clearly formatted.
    - If the requested data does not exist, politely state that based on the current data.
    """

    # 3. Create the Autonomous Agent
    agent = create_pandas_dataframe_agent(
        llm,
        [current_df, master_df], # Pass both dataframes
        verbose=True,            # Set to True so you can watch it "think" in your terminal!
        allow_dangerous_code=True, # Required because the AI is executing real Python code
        prefix=system_prefix
    )

    # 4. Let the Agent solve the problem
    try:
        # The agent will write code, check the output, and formulate a response
        response = agent.invoke({"input": user_query})
        return response["output"]
    except Exception as e:
        return f"The agent encountered an error while thinking: {str(e)}"

if __name__ == "__main__":
    print("Agentic App Engine Loaded.")
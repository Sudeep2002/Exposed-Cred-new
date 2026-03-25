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
    You are an elite Security Data Analyst working with two pandas DataFrames:
    - df1: The 'current batch' of exposed credentials (columns: email, exposure_date, source)
    - df2: The 'master data' of historical exposures (columns: email, last_exposed_date, source)
    
    COMPANY BUSINESS RULES:
    - "Password Reset Needed": This means an email exists in the current batch (df1) BUT DOES NOT exist in the master data (df2).
    - "Repeated User" / "Safe User": This means an email exists in BOTH df1 AND df2.
    
    Write python code to calculate the answer based on these rules. Return only the final answer.
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
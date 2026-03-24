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
        model="llama3.2", 
        base_url="http://localhost:11434",
        temperature=0,
        client_kwargs={"timeout": 120}
    )

    # 2. Give the agent a strict persona and instructions
    # We pass BOTH dataframes as a list: df1 is current_batch, df2 is master_data
    system_prefix = """
    You are an elite Security Data Analyst. 
    You have been given two pandas DataFrames:
    - df1: The 'current batch' of exposed credentials (columns: email, exposure_date, source)
    - df2: The 'master data' of historical exposures (columns: email, last_exposed_date, source)
    
    CRITICAL RULES:
    1. A 'Password Reset' is required IF a user is in df1 BUT NOT in df2 within the last 6 months.
    2. Write python code to calculate the exact answer.
    3. Return ONLY the final answer in a clear, professional sentence. 
    4. If the user asks for a list, provide the emails clearly.
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
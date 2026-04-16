from langchain_ollama import OllamaLLM
from langchain_core.prompts import ChatPromptTemplate

# We only need the analysis prompt now!
analysis_prompt = ChatPromptTemplate.from_messages([
    ("system",
     "You are a security data analyst specializing in exposed credential analysis.\n"
     "Your ONLY job is to answer the user's question using the provided context data.\n\n"
     "CRITICAL RULES:\n"
     "1. Answer ONLY based on the data provided - do NOT infer or guess\n"
     "2. For COUNT questions: respond with ONLY the number\n"
     "3. For LIST questions: provide a clean list with emails\n"
     "4. For FILTERED queries (by source/date): count/list ONLY matching records\n"
     "5. Be concise and factual\n"
     "6. If the question cannot be answered from the data, state that clearly"),
    ("human", "Question: {query}\n\nContext Data:\n{data}")
])

_analysis_chain = None

def _get_analysis_chain():
    global _analysis_chain
    if _analysis_chain is None:
        llm = OllamaLLM(
            model="qwen2.5-coder:7b",
            base_url="http://localhost:11434",
            temperature=0,
            # INCREASED TIMEOUT: Gives your local machine plenty of time to respond
            client_kwargs={"timeout": 120} 
        )
        _analysis_chain = analysis_prompt | llm
    return _analysis_chain

class _LazyAnalysisChain:
    def invoke(self, *args, **kwargs):
        return _get_analysis_chain().invoke(*args, **kwargs)

analysis_chain = _LazyAnalysisChain()
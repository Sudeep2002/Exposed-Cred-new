from langchain_ollama import OllamaLLM
from langchain_core.prompts import ChatPromptTemplate

INTENTS = """
RESET_COUNT
RESET_LIST
RECENT_EXPOSED_COUNT
RECENT_EXPOSED_LIST
SOURCE_BREAKDOWN
UNKNOWN
"""

prompt = ChatPromptTemplate.from_messages([
    ("system",
     "You are an intent classification engine.\n"
     "Classify the user query into EXACTLY ONE intent from this list:\n"
     f"{INTENTS}\n"
     "Return ONLY the intent name.\n"
     "If unclear, return UNKNOWN."),
    ("human", "{query}")
])

# Prompt for generic data analysis
analysis_prompt = ChatPromptTemplate.from_messages([
    ("system",
     "You are a security data analyst specializing in exposed credential analysis.\n"
     "Your ONLY job is to answer the user's question using the provided data.\n\n"
     "CRITICAL RULES:\n"
     "1. Answer ONLY based on the data provided - do NOT infer or guess\n"
     "2. For COUNT questions: respond with ONLY the number\n"
     "3. For LIST questions: provide a clean list with emails\n"
     "4. For FILTERED queries (by source/date): count/list ONLY matching records\n"
     "5. Be concise and factual\n"
     "6. If the question cannot be answered from the data, state that clearly"),
    ("human", "{data}")
])

_intent_chain = None
_analysis_chain = None

def _get_intent_chain():
    global _intent_chain
    if _intent_chain is None:
        llm = OllamaLLM(
            model="mistral",
            base_url="http://localhost:11434",
            temperature=0,
            client_kwargs={"timeout": 20}
        )
        _intent_chain = prompt | llm
    return _intent_chain

def _get_analysis_chain():
    global _analysis_chain
    if _analysis_chain is None:
        llm = OllamaLLM(
            model="mistral",
            base_url="http://localhost:11434",
            temperature=0,
            client_kwargs={"timeout": 20}
        )
        _analysis_chain = analysis_prompt | llm
    return _analysis_chain

class _LazyChain:
    def invoke(self, *args, **kwargs):
        return _get_intent_chain().invoke(*args, **kwargs)

class _LazyAnalysisChain:
    def invoke(self, *args, **kwargs):
        return _get_analysis_chain().invoke(*args, **kwargs)

intent_chain = _LazyChain()
analysis_chain = _LazyAnalysisChain()

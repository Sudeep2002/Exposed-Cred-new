from langchain_ollama import OllamaLLM
from langchain_core.prompts import ChatPromptTemplate

prompt = ChatPromptTemplate.from_messages([
    ("system",
     "You are a helpful security data analyst.\n"
     "Your task is to take the raw calculated data and format it into a natural, concise answer for the user.\n"
     "CRITICAL RULES:\n"
     "1. Answer ONLY based on the raw data provided.\n"
     "2. Do NOT change numbers, hallucinate emails, or assume anything not in the data.\n"
     "3. If the user asks for a count, just provide the final number clearly."),
    ("human", "User Question: {query}\n\nRaw Data Output: {data}")
])

_formatter_chain = None

def _get_formatter_chain():
    global _formatter_chain
    if _formatter_chain is None:
        llm = OllamaLLM(
            model="mistral",
            base_url="http://localhost:11434",
            temperature=0,
            client_kwargs={"timeout": 20}
        )
        _formatter_chain = prompt | llm
    return _formatter_chain

class _LazyChain:
    def invoke(self, *args, **kwargs):
        return _get_formatter_chain().invoke(*args, **kwargs)

formatter_chain = _LazyChain()
from langchain_ollama import OllamaLLM
from langchain_core.prompts import ChatPromptTemplate

prompt = ChatPromptTemplate.from_messages([
    ("system",
     "You are a security data analyst.\n"
     "Answer ONLY based on the provided data.\n"
     "For count questions: provide just the number.\n"
     "For list questions: provide formatted email list.\n"
     "For analysis: be concise and factual.\n"
     "Do NOT infer or assume anything not in the data."),
    ("human", "{data}")
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

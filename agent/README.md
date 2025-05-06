minimal "working" langchain example
- queries pubmed api for info about drug 
- returns relevance and confidence scores, 0 to 100 for relevance from not relevant to highly relevant, as well 0 to 100 for confidence on prediction
- includes rationale

to run: 
    pip install langchain langgraph langchain-openai httpx pytest typing_extensions
    export OPENAI_API_KEY="sk-..."
    python -m pytest -q
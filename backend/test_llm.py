# backend/test_llm.py
from dotenv import load_dotenv
import os

# load .env from backend directory
load_dotenv()

from app.services.llm_agent import LLMAgent

llm = LLMAgent()
print("LLM available:", llm.available)
print("Summary:", llm.summarize("OpenAI builds large models to help researchers and developers."))

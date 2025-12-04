import os
from dotenv import load_dotenv

# Resolve absolute path to backend/.env
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ENV_PATH = os.path.join(BASE_DIR, ".env")

# Load .env (absolute path ensures it works from any working directory)
load_dotenv(ENV_PATH)

class Config:
    OPENAI_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL")
    HF_TOKEN = os.getenv("HF_TOKEN")

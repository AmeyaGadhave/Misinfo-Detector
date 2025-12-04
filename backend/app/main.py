from dotenv import load_dotenv
import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ENV_PATH = os.path.join(BASE_DIR, ".env")

load_dotenv(ENV_PATH)




from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers.detect import router as detect_router

app = FastAPI(title="Misinformation Detector API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"status": "ok", "message": "Backend running"}

app.include_router(detect_router, prefix="/api")


from fastapi import FastAPI
from pydantic import BaseModel
import requests

app = FastAPI(title="Local Vision AI")

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "gemma4:e2b"

class AnalyzeRequest(BaseModel):
    text: str

@app.get("/")
def home():
    return {"message": "Local Vision AI backend is running"}

@app.post("/analyze")
def analyze(request: AnalyzeRequest):
    prompt = f"""
    Analyze the following webpage text.
    Return valid JSON with these keys:
    overview, summary, key_points, important_terms,
    data_insights, visual_explanation, slide_outline.

    Webpage text:
    {request.text}
    """

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "prompt": prompt,
            "stream": False,
            "format": "json"
        },
        timeout=180
    )
    response.raise_for_status()
    return {"result": response.json()["response"]}

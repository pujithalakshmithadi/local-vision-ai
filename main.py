
import json
import re
import subprocess
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from html.parser import HTMLParser

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field


# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
OLLAMA_MODEL = "gemma4:e2b"

app = FastAPI(title="Local Vision AI API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------
# REQUEST MODELS
# --------------------------------------------------

class TextRequest(BaseModel):
    text: str = Field(min_length=1, max_length=100000)


class AskRequest(BaseModel):
    text: str = Field(min_length=1, max_length=100000)
    question: str = Field(min_length=1, max_length=5000)


class URLRequest(BaseModel):
    url: str = Field(min_length=8, max_length=2048)


# --------------------------------------------------
# OLLAMA CONNECTION
# --------------------------------------------------

def call_ollama(prompt: str, json_mode: bool = False) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.3,
            "num_ctx": 8192,
            "num_predict": 2048,
        },
    }

    if json_mode:
        payload["format"] = "json"

    request = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=600) as response:
            result = json.loads(response.read().decode("utf-8"))

        answer = result.get("response", "").strip()

        if not answer:
            raise HTTPException(
                status_code=502,
                detail="Ollama returned an empty response.",
            )

        return answer

    except HTTPException:
        raise

    except urllib.error.URLError as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Could not connect to Ollama. "
                "Check that Ollama is running and the model is installed. "
                f"Details: {exc}"
            ),
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"AI generation failed: {exc}",
        )


def parse_json_response(raw: str) -> dict:
    """Parse JSON returned by the local AI model."""
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)

        if not match:
            raise HTTPException(
                status_code=502,
                detail="AI did not return valid JSON. Please try again.",
            )

        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=502,
                detail="AI returned malformed JSON. Please try again.",
            )

    if not isinstance(data, dict):
        raise HTTPException(
            status_code=502,
            detail="AI returned an unexpected response format.",
        )

    return data


def clean_string_list(value, limit=30):
    if not isinstance(value, list):
        return []

    result = []
    for item in value[:limit]:
        if isinstance(item, str) and item.strip():
            result.append(item.strip())
        elif isinstance(item, dict):
            result.append(json.dumps(item, ensure_ascii=False))

    return result


# --------------------------------------------------
# WEBPAGE TEXT EXTRACTION
# --------------------------------------------------

class PageTextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip_depth = 0
        self.skip_tags = {
            "script", "style", "noscript", "svg",
            "nav", "footer", "header",
        }

    def handle_starttag(self, tag, attrs):
        if tag.lower() in self.skip_tags:
            self.skip_depth += 1

    def handle_endtag(self, tag):
        if tag.lower() in self.skip_tags and self.skip_depth > 0:
            self.skip_depth -= 1

    def handle_data(self, data):
        if not self.skip_depth:
            text = data.strip()
            if text:
                self.parts.append(text)


def fetch_page_text(url: str) -> str:
    # Basic protection against non-web URLs and local network targets.
    from urllib.parse import urlparse
    import ipaddress
    import socket

    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise HTTPException(
            status_code=400,
            detail="Please provide a valid HTTP or HTTPS webpage URL.",
        )

    host = parsed.hostname.lower()

    if host in ("localhost", "localhost.localdomain"):
        raise HTTPException(
            status_code=400,
            detail="Local URLs are not supported by this endpoint.",
        )

    try:
        addresses = socket.getaddrinfo(host, None)
        for address in addresses:
            ip_text = address[4][0]
            ip = ipaddress.ip_address(ip_text)

            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_reserved
                or ip.is_unspecified
            ):
                raise HTTPException(
                    status_code=400,
                    detail="URLs resolving to local or private networks are blocked.",
                )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Could not validate the webpage hostname.",
        )

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "LocalVisionAI/1.0",
            "Accept": "text/html,text/plain",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            content_type = response.headers.get("Content-Type", "")

            if not any(
                kind in content_type.lower()
                for kind in ("text/html", "text/plain")
            ):
                raise HTTPException(
                    status_code=415,
                    detail="This URL does not appear to contain HTML or plain text.",
                )

            raw = response.read(2_000_000)
            charset = response.headers.get_content_charset() or "utf-8"
            html = raw.decode(charset, errors="replace")

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Could not fetch webpage: {exc}",
        )

    parser = PageTextParser()
    parser.feed(html)
    text = re.sub(r"\s+", " ", " ".join(parser.parts)).strip()

    if len(text) < 50:
        raise HTTPException(
            status_code=422,
            detail="Not enough readable text was found on this webpage.",
        )

    return text[:30000]


# --------------------------------------------------
# BASIC ENDPOINT
# --------------------------------------------------

@app.get("/")
def home():
    return {
        "message": "Local Vision AI backend is running!",
        "model": OLLAMA_MODEL,
        "endpoints": [
            "/analyze",
            "/ask",
            "/analyze-url",
            "/generate-slides",
            "/create-pptx",
            "/docs",
        ],
    }


# --------------------------------------------------
# ANALYZE TEXT
# --------------------------------------------------

@app.post("/analyze")
def analyze_text(request: TextRequest):
    prompt = f"""
You are Local Vision AI, an educational assistant.

Analyze the source text carefully. Preserve its important facts,
technical terms, definitions, examples, processes and conclusions.

Return valid JSON with these keys:
- overview: a clear paragraph
- summary: a detailed summary
- key_points: array of meaningful key points
- important_terms: array of important terms and definitions
- data_insights: array of facts, numbers or insights present in the text
- visual_explanation: a simple explanation of any process or diagram described
- slide_outline: array of suggested slide titles

Do not invent facts. If a category is not present in the source,
return an empty array for that category.

SOURCE TEXT:
{request.text[:24000]}
"""

    raw = call_ollama(prompt, json_mode=True)
    data = parse_json_response(raw)

    return {
        "overview": str(data.get("overview", "")),
        "summary": str(data.get("summary", "")),
        "key_points": clean_string_list(data.get("key_points")),
        "important_terms": clean_string_list(data.get("important_terms")),
        "data_insights": clean_string_list(data.get("data_insights")),
        "visual_explanation": str(data.get("visual_explanation", "")),
        "slide_outline": clean_string_list(data.get("slide_outline")),
    }


# --------------------------------------------------
# ASK A QUESTION
# --------------------------------------------------

@app.post("/ask")
def ask_question(request: AskRequest):
    prompt = f"""
Answer the user's question using the source text below.

Rules:
- Give a clear, useful explanation.
- Include relevant details and examples from the source.
- Preserve important technical terminology.
- If the answer is not available in the source, say so honestly.
- Do not invent source-specific facts.

SOURCE TEXT:
{request.text[:24000]}

QUESTION:
{request.question}
"""

    return {"answer": call_ollama(prompt)}


# --------------------------------------------------
# ANALYZE A WEBPAGE URL
# --------------------------------------------------

@app.post("/analyze-url")
def analyze_url(request: URLRequest):
    page_text = fetch_page_text(request.url)

    result = analyze_text(TextRequest(text=page_text))
    result["source_url"] = request.url

    return result


# --------------------------------------------------
# GENERATE DETAILED POWERPOINT SLIDES
# --------------------------------------------------

@app.post("/generate-slides")
def generate_slides(request: TextRequest):
    source_text = request.text.strip()

    if len(source_text) < 80:
        raise HTTPException(
            status_code=422,
            detail=(
                "Please provide more source content so the AI can create "
                "informative slides."
            ),
        )

    prompt = f"""
You are an expert educational presentation designer for Local Vision AI.

Create a DETAILED PowerPoint presentation from the source material.
The audience should understand the topic by reading the slides.

CONTENT REQUIREMENTS:
1. Generate exactly 5 slides.
2. Each slide must have 3 short bullet points.
3. Add speaker notes of 1 short sentence per slide.
4. Include an introduction, main concepts, applications, and conclusion.
5. Use only facts from the source text.
OUTPUT FORMAT:
Return ONLY valid JSON in this exact structure:
{{
  "presentation_title": "Presentation title",
  "slides": [
    {{
      "title": "Slide title",
      "bullets": [
        "Detailed point with an explanation.",
        "Another meaningful point."
      ],
      "speaker_notes": "A detailed explanation for the presenter."
    }}
  ]
}}

Do not include Markdown fences or any text outside the JSON.
The slides array must contain actual slide objects, not strings.
Each slide must have a title, bullets array, and speaker_notes string.

SOURCE MATERIAL:
{source_text[:24000]}
"""

    raw = call_ollama(prompt, json_mode=True)
    data = parse_json_response(raw)

    title = data.get("presentation_title", "Local Vision AI Presentation")
    if not isinstance(title, str) or not title.strip():
        title = "Local Vision AI Presentation"

    raw_slides = data.get("slides", [])

    if not isinstance(raw_slides, list) or not raw_slides:
        raise HTTPException(
            status_code=502,
            detail="AI did not generate any slides. Please try again.",
        )

    slides = []

    for item in raw_slides[:12]:
        if not isinstance(item, dict):
            continue

        slide_title = item.get("title", "Untitled Slide")
        if not isinstance(slide_title, str):
            slide_title = "Untitled Slide"

        bullets = clean_string_list(item.get("bullets"), limit=8)
        notes = item.get("speaker_notes", "")

        if not isinstance(notes, str):
            notes = str(notes)

        if not bullets:
            continue

        slides.append({
            "title": slide_title.strip()[:200],
            "bullets": bullets,
            "speaker_notes": notes.strip(),
        })

    if not slides:
        raise HTTPException(
            status_code=502,
            detail="AI generated slides without usable bullet points.",
        )

    return {
        "presentation_title": title.strip(),
        "slides": slides,
    }


# --------------------------------------------------
# CREATE AND DOWNLOAD THE PPTX
# --------------------------------------------------

@app.post("/create-pptx")
def create_pptx(payload: dict):
    js_file = BASE_DIR / "create_pptx.js"

    if not js_file.exists():
        raise HTTPException(
            status_code=500,
            detail=(
                "create_pptx.js is missing. "
                "Place it inside the local-vision-ai project folder."
            ),
        )

    slides = payload.get("slides")

    if not isinstance(slides, list) or not slides:
        raise HTTPException(
            status_code=422,
            detail="No slides were provided for PowerPoint generation.",
        )

    # Validate the slide data before calling Node.js.
    for slide in slides:
        if not isinstance(slide, dict):
            raise HTTPException(
                status_code=422,
                detail="Each slide must be a JSON object.",
            )

        if not isinstance(slide.get("bullets", []), list):
            raise HTTPException(
                status_code=422,
                detail="Slide bullets must be a list.",
            )

    input_file = None
    output_file = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".json",
            prefix="lva_input_",
            dir=BASE_DIR,
            delete=False,
        ) as temp_input:
            json.dump(payload, temp_input, ensure_ascii=False)
            input_file = Path(temp_input.name)

        with tempfile.NamedTemporaryFile(
            suffix=".pptx",
            prefix="lva_presentation_",
            dir=BASE_DIR,
            delete=False,
        ) as temp_output:
            output_file = Path(temp_output.name)

        result = subprocess.run(
            [
                "node",
                str(js_file),
                str(input_file),
                str(output_file),
            ],
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            details = (result.stderr or result.stdout or "Unknown Node.js error")[-3000:]
            raise HTTPException(
                status_code=500,
                detail=f"PowerPoint generation failed: {details}",
            )

        if not output_file.exists() or output_file.stat().st_size == 0:
            raise HTTPException(
                status_code=500,
                detail="The PowerPoint file was not created.",
            )

        # FileResponse streams the generated file to the browser.
        # Keep the output file until the response has been sent.
        from starlette.background import BackgroundTask

        return FileResponse(
            path=str(output_file),
            media_type=(
                "application/vnd.openxmlformats-officedocument."
                "presentationml.presentation"
            ),
            filename="local_vision_ai_presentation.pptx",
            background=BackgroundTask(
                cleanup_files, input_file, output_file
            ),
        )

    except HTTPException:
        if input_file and input_file.exists():
            input_file.unlink(missing_ok=True)
        if output_file and output_file.exists():
            output_file.unlink(missing_ok=True)
        raise

    except subprocess.TimeoutExpired:
        if input_file and input_file.exists():
            input_file.unlink(missing_ok=True)
        if output_file and output_file.exists():
            output_file.unlink(missing_ok=True)

        raise HTTPException(
            status_code=504,
            detail="PowerPoint generation took too long. Please try again.",
        )

    except Exception as exc:
        if input_file and input_file.exists():
            input_file.unlink(missing_ok=True)
        if output_file and output_file.exists():
            output_file.unlink(missing_ok=True)

        raise HTTPException(
            status_code=500,
            detail=f"Could not create PowerPoint: {exc}",
        )


def cleanup_files(*paths):
    for path in paths:
        if path:
            try:
                Path(path).unlink(missing_ok=True)
            except OSError:
                pass

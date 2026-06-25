import json
import os
import re
import tempfile
import time
from pathlib import Path
from typing import List, Dict, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from faster_whisper import WhisperModel

APP_VERSION = "streaming-0.1"
MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "base")
DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
MIN_TRANSCRIBE_SECONDS = float(os.getenv("STREAM_MIN_SECONDS", "8"))
MAX_BUFFER_MB = int(os.getenv("STREAM_MAX_BUFFER_MB", "50"))

app = FastAPI(title="ClaimRadar BG Streaming STT", version=APP_VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_model = None

SOURCE_LINKS = {
    "НСИ": "https://www.nsi.bg/",
    "БНБ": "https://www.bnb.bg/",
    "НОИ": "https://www.nssi.bg/",
    "НАП": "https://nra.bg/",
    "ЦИК": "https://www.cik.bg/",
    "Народно събрание": "https://www.parliament.bg/",
    "Държавен вестник": "https://dv.parliament.bg/",
    "Министерство на финансите": "https://www.minfin.bg/",
    "Евростат": "https://ec.europa.eu/eurostat/",
    "Factcheck.bg": "https://factcheck.bg/",
    "БТА": "https://www.bta.bg/",
    "БНР": "https://bnr.bg/",
}
TOPIC_SOURCES = {
    "икономика": ["НСИ", "БНБ", "Евростат"],
    "инфлация": ["НСИ", "Евростат", "БНБ"],
    "пенсии": ["НОИ", "НСИ"],
    "данъци": ["НАП", "Министерство на финансите"],
    "избори": ["ЦИК", "Народно събрание"],
    "закони": ["Народно събрание", "Държавен вестник"],
    "друго": ["Factcheck.bg", "БТА", "БНР", "НСИ"],
}
KEYWORDS = {
    "инфлация": ["инфлация", "цени", "поскъп", "ипц", "храни", "горива"],
    "пенсии": ["пенсия", "пенсии", "пенсионер", "нои", "осигур"],
    "данъци": ["данък", "данъци", "ддс", "акциз", "нап"],
    "избори": ["избор", "избори", "цик", "мандат", "партия", "глас"],
    "закони": ["закон", "парламент", "народно събрание", "депутат", "държавен вестник"],
    "икономика": ["бвп", "иконом", "безработ", "заплати", "доходи", "растеж", "инвестиции"],
}
SUBJECTIVE = ["мисля", "според мен", "вярвам", "ужасен", "страхотен", "предател", "мафия", "срам"]


def get_model() -> WhisperModel:
    global _model
    if _model is None:
        _model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)
    return _model


def topic_for(sentence: str) -> str:
    text = sentence.lower()
    best_topic = "друго"
    best_score = 0
    for topic, words in KEYWORDS.items():
        score = sum(1 for word in words if word in text)
        if score > best_score:
            best_topic, best_score = topic, score
    return best_topic


def score_claim(sentence: str):
    low = sentence.lower()
    score = 18
    reasons = []
    if re.search(r"\d", sentence):
        score += 32
        reasons.append("число/година")
    if any(x in low for x in ["%", "процент", "милиона", "милиарда", "млн", "млрд", "лв", "евро"]):
        score += 20
        reasons.append("мерима стойност")
    if any(x in low for x in ["повече", "по-малко", "увелич", "намал", "спрямо", "най-"]):
        score += 18
        reasons.append("сравнение")
    if any(word in low for words in KEYWORDS.values() for word in words):
        score += 15
        reasons.append("публична тема")
    if any(x in low for x in SUBJECTIVE):
        score -= 25
        reasons.append("възможно мнение")
    score = max(5, min(96, score))
    if score >= 70:
        label = "вероятно проверимо"
    elif score >= 45:
        label = "за проверка"
    elif any(x in low for x in SUBJECTIVE):
        label = "мнение"
    else:
        label = "нужни са източници"
    return score, label, ", ".join(reasons) or "streaming speech-to-text"


def analyze_claims(text: str) -> List[Dict[str, Any]]:
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", re.sub(r"\s+", " ", text or "")) if len(s.strip()) > 25]
    claims = []
    for sentence in sentences[-20:]:
        score, label, reason = score_claim(sentence)
        if score < 35:
            continue
        topic = topic_for(sentence)
        sources = [{"name": name, "url": SOURCE_LINKS[name]} for name in TOPIC_SOURCES.get(topic, TOPIC_SOURCES["друго"])]
        claims.append({
            "claim": sentence,
            "topic": topic,
            "label": label,
            "confidence": score,
            "reason": reason,
            "sources": sources,
        })
    return claims[-8:]


def transcribe_buffer(buffer: bytearray, suffix: str = ".webm") -> str:
    if not buffer:
        return ""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        tmp.write(buffer)
        tmp.close()
        segments, _ = get_model().transcribe(tmp.name, language="bg", beam_size=1, vad_filter=True)
        return " ".join(seg.text.strip() for seg in segments).strip()
    finally:
        try:
            Path(tmp.name).unlink(missing_ok=True)
        except Exception:
            pass


@app.get("/health")
def health():
    return {"ok": True, "version": APP_VERSION, "model": MODEL_SIZE, "device": DEVICE, "compute_type": COMPUTE_TYPE}


@app.websocket("/ws/transcribe")
async def ws_transcribe(websocket: WebSocket):
    await websocket.accept()
    buffer = bytearray()
    transcript = ""
    last_transcribe = 0.0
    suffix = ".webm"
    started = time.time()
    try:
        await websocket.send_text(json.dumps({"status": "Streaming backend connected.", "partial": True}, ensure_ascii=False))
        while True:
            message = await websocket.receive()
            if "text" in message:
                try:
                    payload = json.loads(message["text"])
                except json.JSONDecodeError:
                    payload = {"type": "text", "value": message["text"]}
                if payload.get("mimeType", "").startswith("audio/webm"):
                    suffix = ".webm"
                if payload.get("type") == "stop":
                    transcript = transcribe_buffer(buffer, suffix=suffix)
                    await websocket.send_text(json.dumps({
                        "status": "Final transcript ready.",
                        "transcript": transcript,
                        "claims": analyze_claims(transcript),
                        "partial": False,
                    }, ensure_ascii=False))
                    break
                continue

            if "bytes" in message:
                buffer.extend(message["bytes"])
                max_bytes = MAX_BUFFER_MB * 1024 * 1024
                if len(buffer) > max_bytes:
                    buffer = buffer[-max_bytes:]
                now = time.time()
                if now - last_transcribe >= MIN_TRANSCRIBE_SECONDS:
                    last_transcribe = now
                    transcript = transcribe_buffer(buffer, suffix=suffix)
                    await websocket.send_text(json.dumps({
                        "status": f"Partial transcript: {len(transcript)} chars, {int(now - started)} sec.",
                        "transcript": transcript,
                        "claims": analyze_claims(transcript),
                        "partial": True,
                    }, ensure_ascii=False))
    except WebSocketDisconnect:
        return
    except Exception as exc:
        await websocket.send_text(json.dumps({"status": "Streaming error: " + str(exc), "partial": True}, ensure_ascii=False))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("STREAM_PORT", "7861")))

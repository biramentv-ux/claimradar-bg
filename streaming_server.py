import json
import os
import re
import tempfile
import time
from pathlib import Path
from typing import List, Dict, Any, Tuple

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from faster_whisper import WhisperModel

APP_VERSION = "realtime-1.0"
MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "small")
DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
REALTIME_INTERVAL = float(os.getenv("REALTIME_INTERVAL", "1.6"))
ROLLING_WINDOW_MB = int(os.getenv("ROLLING_WINDOW_MB", "18"))
MAX_BUFFER_MB = int(os.getenv("STREAM_MAX_BUFFER_MB", "80"))
LANGUAGE = os.getenv("STREAM_LANGUAGE", "bg")

app = FastAPI(title="ClaimRadar BG Realtime STT", version=APP_VERSION)
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
    return score, label, ", ".join(reasons) or "realtime speech-to-text"


def analyze_claims(text: str) -> List[Dict[str, Any]]:
    sentences = [
        s.strip()
        for s in re.split(r"(?<=[.!?])\s+|\n+", re.sub(r"\s+", " ", text or ""))
        if len(s.strip()) > 25
    ]
    claims = []
    for sentence in sentences[-20:]:
        score, label, reason = score_claim(sentence)
        if score < 35:
            continue
        topic = topic_for(sentence)
        sources = [{"name": name, "url": SOURCE_LINKS[name]} for name in TOPIC_SOURCES.get(topic, TOPIC_SOURCES["друго"])]
        claims.append({"claim": sentence, "topic": topic, "label": label, "confidence": score, "reason": reason, "sources": sources})
    return claims[-8:]


def buffer_to_file(buffer: bytearray, suffix: str = ".webm") -> str:
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(buffer)
    tmp.close()
    return tmp.name


def transcribe_buffer(buffer: bytearray, suffix: str = ".webm", word_timestamps: bool = False) -> Tuple[str, List[Dict[str, Any]]]:
    if not buffer:
        return "", []
    tmp_path = buffer_to_file(buffer, suffix)
    try:
        segments, _ = get_model().transcribe(
            tmp_path,
            language=LANGUAGE,
            beam_size=1,
            best_of=1,
            vad_filter=True,
            word_timestamps=word_timestamps,
            condition_on_previous_text=False,
            without_timestamps=False,
        )
        text_parts = []
        words = []
        for seg in segments:
            seg_text = (seg.text or "").strip()
            if seg_text:
                text_parts.append(seg_text)
            if word_timestamps and getattr(seg, "words", None):
                for word in seg.words:
                    token = (word.word or "").strip()
                    if token:
                        words.append({"word": token, "start": float(word.start or 0), "end": float(word.end or 0), "probability": float(word.probability or 0)})
        return " ".join(text_parts).strip(), words
    finally:
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except Exception:
            pass


def normalize_words(words: List[Dict[str, Any]]) -> List[str]:
    return [re.sub(r"\s+", " ", w.get("word", "")).strip() for w in words if w.get("word")]


def diff_new_words(previous: List[str], current: List[str]) -> List[str]:
    if not current:
        return []
    if not previous:
        return current
    max_overlap = min(len(previous), len(current), 80)
    overlap = 0
    for size in range(max_overlap, 0, -1):
        if previous[-size:] == current[:size]:
            overlap = size
            break
    if overlap:
        return current[overlap:]
    joined_prev = " ".join(previous[-40:]).lower()
    start = 0
    for i, word in enumerate(current):
        if word.lower() not in joined_prev:
            start = i
            break
    return current[start:]


def trim_buffer(buffer: bytearray, max_mb: int) -> bytearray:
    max_bytes = max_mb * 1024 * 1024
    if len(buffer) <= max_bytes:
        return buffer
    return bytearray(buffer[-max_bytes:])


@app.get("/health")
def health():
    return {"ok": True, "version": APP_VERSION, "model": MODEL_SIZE, "device": DEVICE, "compute_type": COMPUTE_TYPE, "language": LANGUAGE}


async def receive_stream(websocket: WebSocket, realtime: bool):
    await websocket.accept()
    buffer = bytearray()
    suffix = ".webm"
    started = time.time()
    last_transcribe = 0.0
    stable_words: List[str] = []
    stable_text = ""
    await websocket.send_text(json.dumps({"status": "Realtime backend connected.", "partial": True, "words": []}, ensure_ascii=False))
    try:
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
                    transcript, words = transcribe_buffer(buffer, suffix=suffix, word_timestamps=True)
                    await websocket.send_text(json.dumps({
                        "status": "Final transcript ready.",
                        "transcript": transcript,
                        "words": normalize_words(words),
                        "new_words": diff_new_words(stable_words, normalize_words(words)),
                        "claims": analyze_claims(transcript),
                        "partial": False,
                        "elapsed": round(time.time() - started, 2),
                    }, ensure_ascii=False))
                    break
                continue

            if "bytes" in message:
                buffer.extend(message["bytes"])
                buffer = trim_buffer(buffer, MAX_BUFFER_MB)
                now = time.time()
                interval = REALTIME_INTERVAL if realtime else float(os.getenv("STREAM_MIN_SECONDS", "8"))
                if now - last_transcribe < interval:
                    continue
                last_transcribe = now
                rolling = trim_buffer(bytearray(buffer), ROLLING_WINDOW_MB if realtime else MAX_BUFFER_MB)
                transcript, words = transcribe_buffer(rolling, suffix=suffix, word_timestamps=realtime)
                current_words = normalize_words(words) if realtime else transcript.split()
                new_words = diff_new_words(stable_words, current_words)
                if new_words:
                    stable_words.extend(new_words)
                    stable_words = stable_words[-500:]
                stable_text = " ".join(stable_words).strip() or transcript
                await websocket.send_text(json.dumps({
                    "status": f"Realtime: +{len(new_words)} words · {len(stable_text)} chars · {int(now - started)} sec.",
                    "transcript": stable_text,
                    "window_transcript": transcript,
                    "words": current_words[-80:],
                    "new_words": new_words,
                    "claims": analyze_claims(stable_text),
                    "partial": True,
                    "elapsed": round(now - started, 2),
                }, ensure_ascii=False))
    except WebSocketDisconnect:
        return
    except Exception as exc:
        await websocket.send_text(json.dumps({"status": "Realtime error: " + str(exc), "partial": True}, ensure_ascii=False))


@app.websocket("/ws/transcribe")
async def ws_transcribe(websocket: WebSocket):
    await receive_stream(websocket, realtime=False)


@app.websocket("/ws/realtime")
async def ws_realtime(websocket: WebSocket):
    await receive_stream(websocket, realtime=True)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("STREAM_PORT", "7861")))

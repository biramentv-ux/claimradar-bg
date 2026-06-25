import json
import os
import re
import tempfile
import time
import uuid
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html import escape, unescape
from pathlib import Path
from typing import Any, Dict, List, Tuple

import gradio as gr
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from faster_whisper import WhisperModel

APP_TITLE = "ClaimRadar BG"
APP_VERSION = "2.1.1-stable-docker"
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "https://dyrakarmy-claimradar-bg.hf.space")
DISCLAIMER = "Тестов инструмент: резултатите са ориентир за проверка, не окончателна правна, политическа или журналистическа оценка."

MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "base")
DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
LANGUAGE = os.getenv("STREAM_LANGUAGE", "bg")
MAX_MEDIA_MB = int(os.getenv("MAX_MEDIA_MB", "80"))
SEARCH_TIMEOUT = int(os.getenv("SEARCH_TIMEOUT", "8"))
REALTIME_INTERVAL = float(os.getenv("REALTIME_INTERVAL", "2.5"))
ROLLING_WINDOW_MB = int(os.getenv("ROLLING_WINDOW_MB", "12"))
STREAM_MAX_BUFFER_MB = int(os.getenv("STREAM_MAX_BUFFER_MB", "60"))
ADMIN_KEY = os.getenv("ADMIN_KEY", "")

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
CHECKS_FILE = DATA_DIR / "checks.jsonl"
FEEDBACK_FILE = DATA_DIR / "feedback.jsonl"

_model = None

SOURCE_LINKS = {
    "НСИ": "https://www.nsi.bg/",
    "БНБ": "https://www.bnb.bg/",
    "НОИ": "https://www.nssi.bg/",
    "НАП": "https://nra.bg/",
    "ЦИК": "https://www.cik.bg/",
    "Народно събрание": "https://www.parliament.bg/",
    "Държавен вестник": "https://dv.parliament.bg/",
    "Министерски съвет": "https://www.gov.bg/",
    "Министерство на финансите": "https://www.minfin.bg/",
    "Министерство на здравеопазването": "https://www.mh.government.bg/",
    "НЗОК": "https://www.nhif.bg/",
    "МОН": "https://www.mon.bg/",
    "Министерство на енергетиката": "https://www.me.government.bg/",
    "КЕВР": "https://www.dker.bg/",
    "Евростат": "https://ec.europa.eu/eurostat/",
    "Европейска комисия": "https://commission.europa.eu/",
    "Factcheck.bg": "https://factcheck.bg/",
    "БТА": "https://www.bta.bg/",
    "БНР": "https://bnr.bg/",
}
SOURCE_DOMAINS = {
    "НСИ": "nsi.bg",
    "БНБ": "bnb.bg",
    "НОИ": "nssi.bg",
    "НАП": "nra.bg",
    "ЦИК": "cik.bg",
    "Народно събрание": "parliament.bg",
    "Държавен вестник": "dv.parliament.bg",
    "Министерски съвет": "gov.bg",
    "Министерство на финансите": "minfin.bg",
    "Министерство на здравеопазването": "mh.government.bg",
    "НЗОК": "nhif.bg",
    "МОН": "mon.bg",
    "Министерство на енергетиката": "me.government.bg",
    "КЕВР": "dker.bg",
    "Евростат": "ec.europa.eu/eurostat",
    "Европейска комисия": "commission.europa.eu",
    "Factcheck.bg": "factcheck.bg",
    "БТА": "bta.bg",
    "БНР": "bnr.bg",
}
TOPIC_SOURCES = {
    "икономика": ["НСИ", "БНБ", "Евростат"],
    "инфлация": ["НСИ", "Евростат", "БНБ"],
    "пенсии": ["НОИ", "НСИ"],
    "данъци": ["НАП", "Министерство на финансите"],
    "избори": ["ЦИК", "Народно събрание"],
    "закони": ["Народно събрание", "Държавен вестник", "Министерски съвет"],
    "бюджет": ["Министерство на финансите", "Народно събрание", "НСИ"],
    "здравеопазване": ["Министерство на здравеопазването", "НЗОК", "НСИ"],
    "образование": ["МОН", "НСИ"],
    "енергетика": ["Министерство на енергетиката", "КЕВР", "БНБ"],
    "ес": ["Евростат", "Европейска комисия"],
    "друго": ["Factcheck.bg", "БТА", "БНР", "НСИ"],
}
KEYWORDS = {
    "инфлация": ["инфлация", "цени", "поскъп", "ипц", "храни", "горива"],
    "пенсии": ["пенсия", "пенсии", "пенсионер", "нои", "осигур"],
    "данъци": ["данък", "данъци", "ддс", "акциз", "нап"],
    "избори": ["избор", "избори", "цик", "мандат", "партия", "глас"],
    "закони": ["закон", "парламент", "народно събрание", "депутат", "държавен вестник"],
    "бюджет": ["бюджет", "дефицит", "дълг", "финанси", "разходи", "приходи"],
    "здравеопазване": ["здраве", "болница", "нзок", "лекар", "пациент"],
    "образование": ["училище", "учител", "мон", "образование", "университет"],
    "енергетика": ["ток", "газ", "енерг", "кевр", "електро", "петрол"],
    "ес": ["ес", "европа", "евростат", "европейски", "шенген", "еврозона"],
    "икономика": ["бвп", "иконом", "безработ", "заплати", "доходи", "растеж", "инвестиции"],
}
SUBJECTIVE_MARKERS = ["мисля", "според мен", "вярвам", "ужасен", "страхотен", "предател", "мафия", "срам", "най-добър", "най-лош"]
NEGATIVE_EVIDENCE_WORDS = ["невярно", "неверно", "подвеждащо", "манипулативно", "дезинформация", "фалшиво", "опроверга"]
POSITIVE_EVIDENCE_WORDS = ["данни", "статистика", "отчет", "доклад", "таблица", "публикация", "резултати"]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def append_jsonl(path: Path, obj: dict):
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def read_jsonl(path: Path, limit=200):
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return list(reversed(rows[-limit:]))


def get_model() -> WhisperModel:
    global _model
    if _model is None:
        _model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)
    return _model


def topic_for(sentence: str) -> str:
    text = sentence.lower()
    best_topic, best_score = "друго", 0
    for topic, words in KEYWORDS.items():
        score = sum(1 for word in words if word in text)
        if score > best_score:
            best_topic, best_score = topic, score
    return best_topic


def source_links(topic: str):
    return [(name, SOURCE_LINKS[name]) for name in TOPIC_SOURCES.get(topic, TOPIC_SOURCES["друго"])]


def split_text(text: str) -> List[str]:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    return [c.strip() for c in re.split(r"(?<=[.!?])\s+|\n+", cleaned) if len(c.strip()) > 20]


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
    if any(x in low for x in ["повече", "по-малко", "увелич", "намал", "спрямо", "най-", "първи", "последни"]):
        score += 18
        reasons.append("сравнение/промяна")
    if any(word in low for words in KEYWORDS.values() for word in words):
        score += 15
        reasons.append("публична тема")
    if any(x in low for x in SUBJECTIVE_MARKERS):
        score -= 25
        reasons.append("възможно мнение")
    score = max(5, min(score, 96))
    if score >= 70:
        label = "вероятно проверимо"
    elif score >= 45:
        label = "за проверка"
    elif any(x in low for x in SUBJECTIVE_MARKERS):
        label = "непроверимо/мнение"
    else:
        label = "нужни са източници"
    return score, label, ", ".join(reasons) or "общо твърдение"


def analyze_claims(text: str, max_claims=30):
    rows = []
    for chunk in split_text(text)[:max_claims]:
        score, label, reason = score_claim(chunk)
        if score < 25 and label != "непроверимо/мнение":
            continue
        topic = topic_for(chunk)
        rows.append({
            "claim": chunk,
            "topic": topic,
            "label": label,
            "confidence": score,
            "reason": reason,
            "sources": [{"name": name, "url": url} for name, url in source_links(topic)],
        })
    return rows


def clean_html(raw):
    text = re.sub(r"<[^>]+>", " ", raw or "")
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_ddg_url(url):
    url = unescape(url or "")
    if url.startswith("//"):
        url = "https:" + url
    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.query)
    if "uddg" in params and params["uddg"]:
        return params["uddg"][0]
    return url


def build_search_url(query):
    return "https://duckduckgo.com/?" + urllib.parse.urlencode({"q": query})


def search_web(query, limit=3):
    search_url = "https://duckduckgo.com/html/?" + urllib.parse.urlencode({"q": query})
    request = urllib.request.Request(search_url, headers={"User-Agent": "Mozilla/5.0 ClaimRadarBG/2.1.1"})
    try:
        with urllib.request.urlopen(request, timeout=SEARCH_TIMEOUT) as response:
            html = response.read().decode("utf-8", errors="ignore")
    except Exception:
        return []
    results = []
    pattern = re.compile(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>.*?(?:<a[^>]+class="result__snippet"[^>]*>(.*?)</a>|<div[^>]+class="result__snippet"[^>]*>(.*?)</div>)', re.S)
    for match in pattern.finditer(html):
        url = normalize_ddg_url(match.group(1))
        title = clean_html(match.group(2))
        snippet = clean_html(match.group(3) or match.group(4) or "")
        if not url.startswith("http") or not title:
            continue
        if any(existing["url"] == url for existing in results):
            continue
        results.append({"title": title[:180], "url": url, "snippet": snippet[:320]})
        if len(results) >= limit:
            break
    return results


def evidence_queries_for_claim(claim, topic):
    claim_short = re.sub(r"\s+", " ", claim).strip()[:160]
    queries = []
    for source_name, _ in source_links(topic)[:4]:
        domain = SOURCE_DOMAINS.get(source_name)
        if domain:
            queries.append((source_name, f"{claim_short} site:{domain}"))
    queries.append(("общо търсене", f"{claim_short} България проверка факти"))
    return queries


def collect_evidence(claim, topic, per_query=2):
    evidence = []
    used_urls = set()
    for source_name, query in evidence_queries_for_claim(claim, topic):
        found = search_web(query, limit=per_query)
        if not found:
            evidence.append({"source": source_name, "title": "Отвори ръчно търсене", "url": build_search_url(query), "snippet": "Автоматичното търсене не върна резултат. Отвори линка и провери ръчно.", "manual": True})
            continue
        for item in found:
            if item["url"] in used_urls:
                continue
            item["source"] = source_name
            item["manual"] = False
            evidence.append(item)
            used_urls.add(item["url"])
        if len([x for x in evidence if not x.get("manual")]) >= 5:
            break
    return evidence[:7]


def evaluate_evidence(evidence):
    real = [item for item in evidence if not item.get("manual")]
    text = " ".join((item.get("title", "") + " " + item.get("snippet", "")).lower() for item in real)
    if not real:
        return "нужна е ръчна проверка", 28, "Не са намерени автоматични резултати."
    if any(word in text for word in NEGATIVE_EVIDENCE_WORDS):
        return "има сигнал за спорно/подвеждащо твърдение", 62, "Намерени са резултати с думи като невярно/подвеждащо/опровергано."
    if len(real) >= 3 and any(word in text for word in POSITIVE_EVIDENCE_WORDS):
        return "има намерени релевантни източници", 70, "Намерени са няколко резултата от надеждни/официални източници."
    return "има първични следи за проверка", 52, "Намерени са резултати, но финалната оценка изисква човешко сравнение."


def render_results(rows):
    if not rows:
        return '<div class="empty-state section-frame">Няма открити ясни проверими твърдения.</div>', "Няма открити ясни проверими твърдения."
    cards = ['<div class="results-grid">']
    copy_lines = [f"ClaimRadar BG v{APP_VERSION}", DISCLAIMER, ""]
    for idx, item in enumerate(rows, 1):
        source_html = "".join([f'<a class="source-chip" href="{escape(src["url"])}" target="_blank">{escape(src["name"])}</a>' for src in item["sources"]])
        confidence = int(item["confidence"])
        cards.append(f'''
<div class="claim-card reveal-card">
  <div class="claim-top"><span class="claim-index">#{idx:02}</span><span class="topic-pill">{escape(item["topic"])}</span><span class="label-pill">{escape(item["label"])}</span></div>
  <div class="claim-text">{escape(item["claim"])}</div>
  <div class="meter shimmer"><span style="width:{confidence}%"></span></div>
  <div class="meta-line">Увереност: <b>{confidence}%</b> · Причина: {escape(item["reason"])}</div>
  <div class="sources-row">{source_html}</div>
  <div class="caution">Провери ръчно преди публикуване.</div>
</div>
''')
        copy_lines += [f"{idx}. [{item['label']}] [{item['topic']}] {item['claim']}", f"Увереност: {confidence}% | Причина: {item['reason']}", "Източници: " + ", ".join([f"{s['name']} - {s['url']}" for s in item["sources"]]), ""]
    cards.append("</div>")
    return "\n".join(cards), "\n".join(copy_lines)


def render_real_check(rows):
    if not rows:
        return '<div class="empty-state section-frame">Няма твърдения за онлайн проверка.</div>', "Няма твърдения за онлайн проверка.", []
    cards = ['<div class="results-grid">']
    copy_lines = [f"ClaimRadar BG v{APP_VERSION} — онлайн проверка", DISCLAIMER, ""]
    saved_items = []
    for idx, item in enumerate(rows[:8], 1):
        evidence = collect_evidence(item["claim"], item["topic"])
        verdict, verdict_score, explanation = evaluate_evidence(evidence)
        ev_html, ev_copy = [], []
        for ev_idx, ev in enumerate(evidence, 1):
            cls = "evidence-link manual" if ev.get("manual") else "evidence-link"
            ev_html.append(f'<a class="{cls}" href="{escape(ev["url"])}" target="_blank"><b>{ev_idx}. {escape(ev.get("source", "източник"))}</b><span>{escape(ev.get("title", "линк"))}</span><small>{escape(ev.get("snippet", ""))}</small></a>')
            ev_copy.append(f'{ev_idx}. {ev.get("source", "източник")}: {ev.get("title", "линк")} — {ev.get("url", "")}')
        cards.append(f'''
<div class="claim-card evidence-card reveal-card">
  <div class="claim-top"><span class="claim-index">LIVE #{idx:02}</span><span class="topic-pill">{escape(item["topic"])}</span><span class="label-pill">{escape(verdict)}</span></div>
  <div class="claim-text">{escape(item["claim"])}</div>
  <div class="meter shimmer"><span style="width:{verdict_score}%"></span></div>
  <div class="meta-line"><b>Индикативна оценка:</b> {escape(verdict)} · {escape(explanation)}</div>
  <div class="evidence-list">{"".join(ev_html)}</div>
  <div class="caution">Това не е финална присъда. Отвори линковете и сравни твърдението с първичните данни.</div>
</div>
''')
        copy_lines += [f"{idx}. {item['claim']}", f"Оценка: {verdict} | {explanation}", *ev_copy, ""]
        saved_items.append({**item, "verdict": verdict, "verdict_score": verdict_score, "explanation": explanation, "evidence": evidence})
    cards.append("</div>")
    return "\n".join(cards), "\n".join(copy_lines), saved_items


def analyze(text):
    rows = analyze_claims(text)
    html, copy_text = render_results(rows)
    return html, copy_text, f"Открити твърдения: {len(rows)}"


def real_check(text):
    rows = analyze_claims(text)
    html, copy_text, _ = render_real_check(rows)
    return html, copy_text, f"Онлайн проверени твърдения: {min(len(rows), 8)}"


def save_public_check(title, text, mode):
    if not (text or "").strip():
        return "", "Няма текст за запазване."
    title = (title or "Публична проверка").strip()[:90]
    check_id = uuid.uuid4().hex[:10]
    if mode == "реална проверка":
        rows = analyze_claims(text)
        html, copy_text, saved_items = render_real_check(rows)
    else:
        saved_items = analyze_claims(text)
        html, copy_text = render_results(saved_items)
    record = {"id": check_id, "created_at": now_iso(), "title": title, "mode": mode, "text_preview": re.sub(r"\s+", " ", text).strip()[:500], "items": saved_items, "html": html, "copy_text": copy_text}
    append_jsonl(CHECKS_FILE, record)
    share = f"{PUBLIC_BASE_URL}?check_id={check_id}"
    return check_id, f"Запазено. ID: {check_id} | Share: {share}"


def load_public_check(check_id):
    check_id = (check_id or "").strip()
    if not check_id:
        return '<div class="empty-state section-frame">Въведи ID на проверка.</div>', ""
    for rec in read_jsonl(CHECKS_FILE, limit=500):
        if rec.get("id") == check_id:
            header = f'<div class="archive-head reveal-card"><b>{escape(rec.get("title", "Проверка"))}</b><span>ID: {escape(check_id)} · {escape(rec.get("created_at", ""))} · {escape(rec.get("mode", ""))}</span></div>'
            return header + rec.get("html", ""), rec.get("copy_text", "")
    return '<div class="empty-state section-frame">Не е намерена проверка с това ID.</div>', ""


def list_public_checks():
    rows = read_jsonl(CHECKS_FILE, limit=30)
    if not rows:
        return '<div class="empty-state section-frame">Все още няма запазени публични проверки.</div>'
    cards = ['<div class="history-grid">']
    for rec in rows:
        cards.append(f'<div class="history-card reveal-card"><b>{escape(rec.get("title", "Проверка"))}</b><span>{escape(rec.get("created_at", ""))} · {escape(rec.get("mode", ""))}</span><code>{escape(rec.get("id", ""))}</code><p>{escape(rec.get("text_preview", ""))}</p></div>')
    cards.append("</div>")
    return "\n".join(cards)


def export_checks():
    rows = read_jsonl(CHECKS_FILE, limit=1000)
    out = tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="w", encoding="utf-8")
    json.dump(rows, out, ensure_ascii=False, indent=2)
    out.close()
    return out.name


def load_txt(file):
    if not file:
        return ""
    path = getattr(file, "name", file)
    try:
        return Path(path).read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return Path(path).read_text(encoding="cp1251", errors="ignore")


def file_size_mb(path):
    try:
        return os.path.getsize(path) / 1024 / 1024
    except OSError:
        return 0


def ts(seconds):
    ms = int((seconds - int(seconds)) * 1000)
    total = int(seconds)
    return f"{total//3600:02}:{(total%3600)//60:02}:{total%60:02},{ms:03}"


def transcribe_file(file_path):
    if not file_path:
        return "", None, "Качи аудио или видео файл."
    path = getattr(file_path, "name", file_path)
    size = file_size_mb(path)
    if size > MAX_MEDIA_MB:
        return "", None, f"Файлът е {size:.1f} MB. Лимитът е {MAX_MEDIA_MB} MB. Качи по-кратък файл."
    segments, _ = get_model().transcribe(path, language=LANGUAGE, beam_size=1, vad_filter=True)
    segments = list(segments)
    transcript = " ".join(seg.text.strip() for seg in segments).strip()
    srt_blocks = [f"{i}\n{ts(seg.start)} --> {ts(seg.end)}\n{seg.text.strip()}\n" for i, seg in enumerate(segments, 1)]
    out = tempfile.NamedTemporaryFile(delete=False, suffix=".srt", mode="w", encoding="utf-8")
    out.write("\n".join(srt_blocks))
    out.close()
    return transcript, out.name, f"Готово. Дължина: {len(transcript)} символа. Модел: {MODEL_SIZE}/{DEVICE}/{COMPUTE_TYPE}"


def transcribe_and_analyze(file_path):
    transcript, srt_file, status = transcribe_file(file_path)
    html, copy_text, count = analyze(transcript)
    return transcript, html, copy_text, srt_file, status + " · " + count


def transcribe_and_real_check(file_path):
    transcript, srt_file, status = transcribe_file(file_path)
    html, copy_text, count = real_check(transcript)
    return transcript, html, copy_text, srt_file, status + " · " + count


def save_feedback(name, email, kind, comment):
    feedback_id = uuid.uuid4().hex[:8]
    append_jsonl(FEEDBACK_FILE, {"id": feedback_id, "created_at": now_iso(), "name": name or "", "email": email or "", "kind": kind, "comment": comment or ""})
    return f"Записано. ID: {feedback_id}"


def admin_panel(key):
    if ADMIN_KEY and key != ADMIN_KEY:
        return '<div class="section-frame admin-card reveal-card"><div class="status-pill danger"><span class="live-dot red"></span> Грешен admin key</div></div>'
    if not ADMIN_KEY:
        return '<div class="section-frame admin-card reveal-card"><div class="status-pill"><span class="live-dot"></span> ADMIN_KEY не е зададен в Space Variables. Админ панелът е заключен.</div></div>'
    checks = read_jsonl(CHECKS_FILE, limit=100)
    feedback = read_jsonl(FEEDBACK_FILE, limit=100)
    html = ["<div class='admin-shell'>"]
    html.append(f"""
<div class="metric-grid">
  <div class="metric-card reveal-card"><div class="metric-label">Saved Checks</div><div class="metric-value">{len(checks)}</div><div class="metric-sub">локален JSONL архив</div></div>
  <div class="metric-card reveal-card"><div class="metric-label">Feedback Items</div><div class="metric-value">{len(feedback)}</div><div class="metric-sub">потребителски сигнали</div></div>
  <div class="metric-card reveal-card"><div class="metric-label">Realtime</div><div class="metric-value"><span class="live-dot"></span> Active</div><div class="metric-sub">/ws/realtime</div></div>
  <div class="metric-card reveal-card"><div class="metric-label">System Mode</div><div class="metric-value">HF Ready</div><div class="metric-sub">{escape(APP_VERSION)}</div></div>
</div>
""")
    html.append("<div class='admin-grid'><div class='admin-card reveal-card'><h3>Последни проверки</h3><div class='timeline'>")
    for rec in checks[:12] or [{"title": "Няма запазени проверки", "created_at": "", "id": ""}]:
        html.append(f'<div class="timeline-item"><b>{escape(rec.get("title", "Проверка"))}</b><br><small>{escape(rec.get("id", ""))} · {escape(rec.get("created_at", ""))}</small></div>')
    html.append("</div></div><div class='admin-card reveal-card'><h3>Feedback поток</h3><div class='timeline'>")
    for fb in feedback[:12] or [{"kind": "Няма feedback", "created_at": "", "comment": ""}]:
        html.append(f'<div class="timeline-item"><b>{escape(fb.get("kind", "друго"))}</b><br><small>{escape(fb.get("created_at", ""))}</small><br><span>{escape(fb.get("comment", ""))}</span></div>')
    html.append("</div></div></div></div>")
    return "".join(html)


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
        segments, _ = get_model().transcribe(tmp_path, language=LANGUAGE, beam_size=1, best_of=1, vad_filter=True, word_timestamps=word_timestamps, condition_on_previous_text=False, without_timestamps=False)
        text_parts, words = [], []
        for seg in segments:
            if (seg.text or "").strip():
                text_parts.append(seg.text.strip())
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
    for size in range(max_overlap, 0, -1):
        if previous[-size:] == current[:size]:
            return current[size:]
    joined_prev = " ".join(previous[-40:]).lower()
    for i, word in enumerate(current):
        if word.lower() not in joined_prev:
            return current[i:]
    return []


def trim_buffer(buffer: bytearray, max_mb: int) -> bytearray:
    max_bytes = max_mb * 1024 * 1024
    if len(buffer) <= max_bytes:
        return buffer
    return bytearray(buffer[-max_bytes:])


async def receive_realtime(websocket: WebSocket, realtime=True):
    await websocket.accept()
    buffer = bytearray()
    suffix = ".webm"
    started = time.time()
    last_transcribe = 0.0
    stable_words: List[str] = []
    await websocket.send_text(json.dumps({"status": "HF realtime backend connected.", "partial": True, "words": [], "version": APP_VERSION}, ensure_ascii=False))
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
                    current_words = normalize_words(words)
                    await websocket.send_text(json.dumps({"status": "Final transcript ready.", "transcript": transcript, "words": current_words, "new_words": diff_new_words(stable_words, current_words), "claims": analyze_claims(transcript, max_claims=20)[-8:], "partial": False, "elapsed": round(time.time() - started, 2)}, ensure_ascii=False))
                    break
                continue
            if "bytes" in message:
                buffer.extend(message["bytes"])
                buffer = trim_buffer(buffer, STREAM_MAX_BUFFER_MB)
                now = time.time()
                interval = REALTIME_INTERVAL if realtime else float(os.getenv("STREAM_MIN_SECONDS", "8"))
                if now - last_transcribe < interval:
                    continue
                last_transcribe = now
                rolling = trim_buffer(bytearray(buffer), ROLLING_WINDOW_MB if realtime else STREAM_MAX_BUFFER_MB)
                transcript, words = transcribe_buffer(rolling, suffix=suffix, word_timestamps=realtime)
                current_words = normalize_words(words) if realtime else transcript.split()
                new_words = diff_new_words(stable_words, current_words)
                if new_words:
                    stable_words.extend(new_words)
                    stable_words = stable_words[-500:]
                stable_text = " ".join(stable_words).strip() or transcript
                await websocket.send_text(json.dumps({"status": f"Realtime: +{len(new_words)} words · {len(stable_text)} chars · {int(now - started)} sec.", "transcript": stable_text, "window_transcript": transcript, "words": current_words[-80:], "new_words": new_words, "claims": analyze_claims(stable_text, max_claims=20)[-8:], "partial": True, "elapsed": round(now - started, 2)}, ensure_ascii=False))
    except WebSocketDisconnect:
        return
    except Exception as exc:
        try:
            await websocket.send_text(json.dumps({"status": "Realtime error: " + str(exc), "partial": True}, ensure_ascii=False))
        except Exception:
            pass


CSS = """
:root{--bg:#020617;--cyan:#22d3ee;--purple:#a855f7;--blue:#2563eb;--text:#f8fafc;--muted:#94a3b8;--border:rgba(34,211,238,.20)}
html,body,.gradio-container{background:radial-gradient(circle at 10% 10%,rgba(34,211,238,.16),transparent 23%),radial-gradient(circle at 86% 12%,rgba(168,85,247,.20),transparent 25%),linear-gradient(180deg,#020617 0%,#071126 100%)!important;color:var(--text)!important}.gradio-container{max-width:1280px!important;margin:auto!important}.gradio-container:before{content:"";position:fixed;inset:0;background-image:linear-gradient(rgba(34,211,238,.05) 1px,transparent 1px),linear-gradient(90deg,rgba(34,211,238,.05) 1px,transparent 1px);background-size:36px 36px;pointer-events:none;animation:gridMove 18s linear infinite;opacity:.38}@keyframes gridMove{to{transform:translateY(36px)}}
#hero-shell{position:relative;border:1px solid rgba(34,211,238,.25);border-radius:30px;overflow:hidden;padding:34px;background:linear-gradient(135deg,rgba(2,6,23,.94),rgba(30,27,75,.74));box-shadow:0 0 44px rgba(34,211,238,.15),inset 0 0 70px rgba(168,85,247,.08)}.hero-kicker{color:var(--cyan);letter-spacing:.22em;text-transform:uppercase;font-size:12px;font-weight:900}.hero-title{font-size:clamp(36px,7vw,76px);line-height:.92;font-weight:950;color:#fff;text-shadow:0 0 24px rgba(34,211,238,.30);margin:12px 0}.hero-subtitle{max-width:930px;color:#cbd5e1;font-size:18px}.metric-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:16px}.metric-card,.section-frame,.claim-card,.history-card,.admin-card{border:1px solid var(--border);background:linear-gradient(135deg,rgba(15,23,42,.80),rgba(30,41,59,.58));border-radius:22px;box-shadow:0 0 28px rgba(34,211,238,.13);backdrop-filter:blur(14px);transition:transform .28s ease,box-shadow .28s ease,border-color .28s ease}.metric-card:hover,.section-frame:hover,.claim-card:hover,.history-card:hover,.admin-card:hover{transform:translateY(-4px);border-color:rgba(34,211,238,.40);box-shadow:0 0 38px rgba(34,211,238,.20)}.metric-card,.claim-card,.history-card,.admin-card{padding:18px}.metric-label{color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.16em}.metric-value{font-size:30px;font-weight:950;color:white;margin-top:8px}.metric-sub{color:#94a3b8;font-size:12px;margin-top:4px}.live-dot{width:10px;height:10px;border-radius:50%;background:#22d3ee;box-shadow:0 0 16px rgba(34,211,238,.85);animation:pulseDot 1.4s infinite;display:inline-block}.live-dot.red{background:#fb7185}@keyframes pulseDot{0%,100%{transform:scale(.9);opacity:.78}50%{transform:scale(1.25);opacity:1}}
.gradio-container textarea,.gradio-container input{background:rgba(2,6,23,.62)!important;color:#f8fafc!important;border:1px solid rgba(34,211,238,.22)!important;border-radius:16px!important}.gr-button-primary{background:linear-gradient(90deg,#0891b2,#7c3aed)!important;border:0!important;box-shadow:0 0 24px rgba(34,211,238,.22)!important}.results-grid,.history-grid,.admin-shell{display:grid;gap:16px}.admin-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(310px,1fr));gap:18px}.claim-top{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:12px}.claim-index{color:#67e8f9;font-family:ui-monospace,monospace;font-weight:950}.topic-pill,.label-pill,.source-chip,.status-pill{display:inline-flex;align-items:center;gap:8px;border-radius:999px;padding:7px 11px;font-size:12px;text-decoration:none}.topic-pill{background:rgba(37,99,235,.18);color:#bfdbfe;border:1px solid rgba(59,130,246,.25)}.label-pill{background:rgba(168,85,247,.18);color:#e9d5ff;border:1px solid rgba(168,85,247,.28)}.status-pill{border:1px solid rgba(34,211,238,.24);background:rgba(8,145,178,.12);color:#cffafe}.status-pill.danger{border-color:rgba(251,113,133,.34);background:rgba(127,29,29,.28);color:#fecdd3}.claim-text{font-size:16px;color:#f8fafc;line-height:1.55}.meter{height:8px;border-radius:999px;background:rgba(148,163,184,.17);overflow:hidden;margin:14px 0 8px}.meter span{display:block;height:100%;background:linear-gradient(90deg,#22d3ee,#a855f7);border-radius:999px}.meta-line{color:#cbd5e1;font-size:13px;margin-bottom:12px}.sources-row{display:flex;flex-wrap:wrap;gap:8px}.source-chip{color:#cffafe!important;border:1px solid rgba(34,211,238,.24);background:rgba(8,145,178,.12)}.evidence-list{display:grid;gap:10px;margin-top:12px}.evidence-link{display:grid;gap:4px;text-decoration:none!important;color:#e0f2fe!important;border:1px solid rgba(34,211,238,.22);background:rgba(2,6,23,.36);border-radius:16px;padding:12px}.evidence-link span{color:#fff}.evidence-link small{color:#94a3b8;line-height:1.35}.evidence-link.manual{border-style:dashed;color:#fde68a!important}.caution{margin-top:12px;color:#fbbf24;font-size:12px}.empty-state{padding:24px;color:#cbd5e1}.footer-note,.history-card span,.history-card p{color:#94a3b8;font-size:13px}.archive-head{border:1px solid rgba(34,211,238,.22);border-radius:18px;padding:14px;margin-bottom:14px;background:rgba(15,23,42,.55);display:grid;gap:4px}.timeline{display:grid;gap:12px}.timeline-item{border-left:2px solid rgba(34,211,238,.30);padding-left:14px;color:#cbd5e1;position:relative}.timeline-item:before{content:"";position:absolute;left:-6px;top:6px;width:10px;height:10px;border-radius:50%;background:var(--cyan);box-shadow:0 0 14px rgba(34,211,238,.60)}
"""

JS_HTML = """
<script>
function claimRadarBoot(){
  document.querySelectorAll('.claim-card,.history-card,.admin-card,.metric-card,.section-frame,.archive-head').forEach((el,i)=>{
    if(!el.dataset.crAnimated){el.dataset.crAnimated='1';el.style.opacity='0';el.style.transform='translateY(18px)';setTimeout(()=>{el.style.transition='opacity .65s ease, transform .65s ease';el.style.opacity='1';el.style.transform='translateY(0)';}, Math.min(i*65,700));}
  });
}
window.addEventListener('load',()=>setTimeout(claimRadarBoot,250));
window.addEventListener('DOMContentLoaded',()=>{new MutationObserver(()=>setTimeout(claimRadarBoot,120)).observe(document.body,{childList:true,subtree:true});});
</script>
"""

HERO = f"""
<div id="hero-shell">
  <div class="hero-kicker">CLAIMRADAR BG · ANIMATED CONTROL CENTER · {APP_VERSION}</div>
  <div class="hero-title">Realtime Fact Intelligence</div>
  <div class="hero-subtitle">Футуристичен интерфейс за откриване, първична проверка, архивиране и realtime проследяване на публични твърдения в България.</div>
  <div class="metric-grid" style="margin-top:24px;">
    <div class="metric-card"><div class="metric-label">Realtime Mode</div><div class="metric-value"><span class="live-dot"></span> Live</div><div class="metric-sub">wss endpoint ready</div></div>
    <div class="metric-card"><div class="metric-label">WebSocket</div><div class="metric-value">/ws/realtime</div><div class="metric-sub">extension bridge</div></div>
    <div class="metric-card"><div class="metric-label">Public Archive</div><div class="metric-value">Share ID</div><div class="metric-sub">JSONL storage</div></div>
    <div class="metric-card"><div class="metric-label">System Status</div><div class="metric-value">Ready</div><div class="metric-sub">HF deployment</div></div>
  </div>
</div>
"""

with gr.Blocks(title=APP_TITLE, theme=gr.themes.Soft(primary_hue="cyan", neutral_hue="slate"), css=CSS) as demo:
    gr.HTML(JS_HTML)
    gr.HTML(HERO)
    gr.Markdown(f"<p class='footer-note'>{DISCLAIMER}</p>")

    with gr.Tab("🚦 Проверка на текст"):
        with gr.Row():
            file = gr.File(label="Качи .txt", file_types=[".txt"])
            title = gr.Textbox(label="Заглавие за запазване", value="Публична проверка")
            status = gr.Textbox(label="Статус", value="Готов за анализ.", interactive=False)
        text = gr.Textbox(label="Текст / транскрипт", lines=12, placeholder="Постави текст от дебат, интервю, реч, новина или парламентарна стенограма...")
        file.change(load_txt, file, text)
        mode = gr.Dropdown(label="Режим за запазване", choices=["бърза проверка", "реална проверка"], value="бърза проверка")
        with gr.Row():
            btn = gr.Button("Провери твърденията", variant="primary")
            real_btn = gr.Button("Реална проверка с източници")
            save_btn = gr.Button("Запази публична проверка")
            gr.ClearButton([text], value="Изчисти")
        result_html = gr.HTML(label="Резултати")
        copy_box = gr.Textbox(label="Копирай резултатите", lines=10, show_copy_button=True)
        share_id = gr.Textbox(label="Share ID / статус", interactive=False)
        btn.click(analyze, text, [result_html, copy_box, status])
        real_btn.click(real_check, text, [result_html, copy_box, status])
        save_btn.click(save_public_check, [title, text, mode], [share_id, status])

    with gr.Tab("🔴 Word realtime"):
        gr.HTML(f"""
<div class="section-frame reveal-card" style="padding:24px;">
  <div class="status-pill"><span class="live-dot"></span> Realtime endpoint ready</div>
  <h2>Extension WebSocket</h2>
  <code>wss://dyrakarmy-claimradar-bg.hf.space/ws/realtime</code>
  <p class="meta-line">Health check: <code>{PUBLIC_BASE_URL}/health</code></p>
</div>
""")

    with gr.Tab("🎙️ Аудио/видео"):
        gr.Markdown(f"Качи кратък файл за публичен тест. Препоръчителен лимит: до **{MAX_MEDIA_MB} MB**.")
        media = gr.File(label="Аудио или видео", file_types=[".mp3", ".wav", ".m4a", ".mp4", ".webm", ".ogg", ".flac", ".aac"])
        audio_title = gr.Textbox(label="Заглавие за запазване", value="Проверка от аудио/видео")
        with gr.Row():
            tr_btn = gr.Button("Само транскрибирай")
            full_btn = gr.Button("Транскрибирай и провери", variant="primary")
            real_media_btn = gr.Button("Транскрибирай и провери онлайн")
            save_audio_btn = gr.Button("Запази транскрипта")
        transcript = gr.Textbox(label="Транскрипция", lines=12, show_copy_button=True)
        media_results = gr.HTML(label="Резултати")
        media_copy = gr.Textbox(label="Копирай резултатите", lines=8, show_copy_button=True)
        srt_file = gr.File(label="Свали .SRT")
        media_status = gr.Textbox(label="Статус", interactive=False)
        audio_share = gr.Textbox(label="Share ID / статус", interactive=False)
        tr_btn.click(transcribe_file, media, [transcript, srt_file, media_status])
        full_btn.click(transcribe_and_analyze, media, [transcript, media_results, media_copy, srt_file, media_status])
        real_media_btn.click(transcribe_and_real_check, media, [transcript, media_results, media_copy, srt_file, media_status])
        save_audio_btn.click(save_public_check, [audio_title, transcript, gr.State("бърза проверка")], [audio_share, media_status])

    with gr.Tab("🗂️ Публичен архив"):
        gr.Markdown("Запазените проверки получават **Share ID**. На free Space записите може да изчезнат при рестарт, ако няма persistent storage.")
        check_id = gr.Textbox(label="Зареди по Share ID")
        with gr.Row():
            load_btn = gr.Button("Зареди проверка", variant="primary")
            refresh_btn = gr.Button("Обнови последните проверки")
            export_btn = gr.Button("Export JSON")
        archive_html = gr.HTML(label="Архив", value=list_public_checks())
        archive_copy = gr.Textbox(label="Копирай заредената проверка", lines=8, show_copy_button=True)
        export_file = gr.File(label="Свали архив")
        load_btn.click(load_public_check, check_id, [archive_html, archive_copy])
        refresh_btn.click(list_public_checks, outputs=archive_html)
        export_btn.click(export_checks, outputs=export_file)

    with gr.Tab("🛰️ Източници"):
        source_md = "## Източници по категории\n\n"
        for topic, names in TOPIC_SOURCES.items():
            links = " · ".join([f"[{name}]({SOURCE_LINKS[name]})" for name in names])
            source_md += f"### {topic}\n{links}\n\n"
        source_md += "\nПърво се проверяват официални първични данни. Медии и fact-check сайтове се използват като допълнителен контекст."
        gr.Markdown(source_md)

    with gr.Tab("📡 Обратна връзка"):
        name = gr.Textbox(label="Име по избор")
        email = gr.Textbox(label="Имейл по избор")
        kind = gr.Dropdown(label="Тип проблем", choices=["грешна категоризация", "липсващ източник", "проблем с интерфейса", "идея за функция", "друго"], value="идея за функция")
        comment = gr.Textbox(label="Коментар", lines=5)
        send = gr.Button("Изпрати", variant="primary")
        feedback_status = gr.Textbox(label="Статус")
        send.click(save_feedback, [name, email, kind, comment], feedback_status)

    with gr.Tab("🛡️ Admin"):
        gr.HTML("<div class='section-frame reveal-card' style='padding:18px;'><span class='status-pill'><span class='live-dot'></span> Animated Admin Control Center</span></div>")
        key = gr.Textbox(label="Admin key", type="password")
        admin_btn = gr.Button("Отвори admin панел", variant="primary")
        admin_html = gr.HTML(label="Admin")
        admin_btn.click(admin_panel, key, admin_html)

    gr.Markdown(f"---\n{DISCLAIMER}")

fastapi_app = FastAPI(title=APP_TITLE, version=APP_VERSION)
fastapi_app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@fastapi_app.get("/health")
def health():
    return JSONResponse({"ok": True, "version": APP_VERSION, "model": MODEL_SIZE, "device": DEVICE, "compute_type": COMPUTE_TYPE, "language": LANGUAGE, "realtime_endpoint": "/ws/realtime", "public_realtime_url": PUBLIC_BASE_URL.replace("https://", "wss://").replace("http://", "ws://") + "/ws/realtime"})


@fastapi_app.websocket("/ws/realtime")
async def ws_realtime(websocket: WebSocket):
    await receive_realtime(websocket, realtime=True)


@fastapi_app.websocket("/ws/transcribe")
async def ws_transcribe(websocket: WebSocket):
    await receive_realtime(websocket, realtime=False)


app = gr.mount_gradio_app(fastapi_app, demo, path="/")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", os.getenv("APP_PORT", "7860"))))

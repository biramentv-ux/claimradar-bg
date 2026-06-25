import os
import re
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path
from html import escape, unescape

import gradio as gr
from faster_whisper import WhisperModel

APP_TITLE = "ClaimRadar BG"
APP_VERSION = "0.3"
DISCLAIMER = "Тестов инструмент: резултатите са ориентир за проверка, не окончателна правна, политическа или журналистическа оценка."
MAX_MEDIA_MB = int(os.getenv("MAX_MEDIA_MB", "80"))
MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "base")
DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
SEARCH_TIMEOUT = int(os.getenv("SEARCH_TIMEOUT", "8"))
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


def get_model():
    global _model
    if _model is None:
        _model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)
    return _model


def topic_for(sentence):
    text = sentence.lower()
    scores = {topic: sum(1 for word in words if word in text) for topic, words in KEYWORDS.items()}
    topic, score = max(scores.items(), key=lambda item: item[1])
    return topic if score else "друго"


def split_text(text):
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    return [c.strip() for c in re.split(r"(?<=[.!?])\s+|\n+", cleaned) if len(c.strip()) > 20]


def score_claim(sentence):
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


def source_links(topic):
    return [(name, SOURCE_LINKS[name]) for name in TOPIC_SOURCES.get(topic, TOPIC_SOURCES["друго"])]


def analyze_claims(text):
    rows = []
    for chunk in split_text(text)[:30]:
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
            "sources": source_links(topic),
        })
    return rows


def clean_html(raw):
    text = re.sub(r"<[^>]+>", " ", raw or "")
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


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
    request = urllib.request.Request(
        search_url,
        headers={"User-Agent": "Mozilla/5.0 ClaimRadarBG/0.3"},
    )
    try:
        with urllib.request.urlopen(request, timeout=SEARCH_TIMEOUT) as response:
            html = response.read().decode("utf-8", errors="ignore")
    except Exception:
        return []

    results = []
    pattern = re.compile(
        r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>.*?(?:<a[^>]+class="result__snippet"[^>]*>(.*?)</a>|<div[^>]+class="result__snippet"[^>]*>(.*?)</div>)',
        re.S,
    )
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
            queries.append((source_name, f'{claim_short} site:{domain}'))
    queries.append(("общо търсене", f'{claim_short} България проверка факти'))
    return queries


def collect_evidence(claim, topic, per_query=2):
    evidence = []
    used_urls = set()
    for source_name, query in evidence_queries_for_claim(claim, topic):
        found = search_web(query, limit=per_query)
        if not found:
            evidence.append({
                "source": source_name,
                "title": "Отвори ръчно търсене",
                "url": build_search_url(query),
                "snippet": "Автоматичното търсене не върна надежден резултат. Отвори линка и провери ръчно.",
                "manual": True,
            })
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
        return "нужна е ръчна проверка", 28, "Не са намерени автоматични резултати; показани са линкове за ръчно търсене."
    if any(word in text for word in NEGATIVE_EVIDENCE_WORDS):
        return "има сигнал за спорно/подвеждащо твърдение", 62, "Намерени са резултати с думи като невярно/подвеждащо/опровергано."
    if len(real) >= 3 and any(word in text for word in POSITIVE_EVIDENCE_WORDS):
        return "има намерени релевантни източници", 70, "Намерени са няколко резултата от надеждни/официални източници."
    if len(real) >= 1:
        return "има първични следи за проверка", 52, "Намерени са резултати, но финалната оценка изисква човешко сравнение с данните."
    return "нужна е ръчна проверка", 30, "Автоматичното търсене е ограничено."


def render_results(rows):
    if not rows:
        return '<div class="empty-state">Няма открити ясни проверими твърдения.</div>', "Няма открити ясни проверими твърдения."
    cards = ['<div class="results-grid">']
    copy_lines = [f"ClaimRadar BG v{APP_VERSION}", DISCLAIMER, ""]
    for idx, item in enumerate(rows, 1):
        source_html = "".join([f'<a class="source-chip" href="{url}" target="_blank">{escape(name)}</a>' for name, url in item["sources"]])
        confidence = int(item["confidence"])
        cards.append(f'''
<div class="claim-card">
  <div class="claim-top">
    <span class="claim-index">#{idx:02}</span>
    <span class="topic-pill">{escape(item["topic"])}</span>
    <span class="label-pill">{escape(item["label"])}</span>
  </div>
  <div class="claim-text">{escape(item["claim"])}</div>
  <div class="meter"><span style="width:{confidence}%"></span></div>
  <div class="meta-line">Увереност: <b>{confidence}%</b> · Причина: {escape(item["reason"])}</div>
  <div class="sources-row">{source_html}</div>
  <div class="caution">Провери ръчно преди публикуване.</div>
</div>
''')
        copy_lines.append(f"{idx}. [{item['label']}] [{item['topic']}] {item['claim']}")
        copy_lines.append(f"Увереност: {confidence}% | Причина: {item['reason']}")
        copy_lines.append("Източници: " + ", ".join([f"{name} - {url}" for name, url in item["sources"]]))
        copy_lines.append("")
    cards.append("</div>")
    return "\n".join(cards), "\n".join(copy_lines)


def render_real_check(rows):
    if not rows:
        return '<div class="empty-state">Няма твърдения за онлайн проверка.</div>', "Няма твърдения за онлайн проверка."
    cards = ['<div class="results-grid">']
    copy_lines = [f"ClaimRadar BG v{APP_VERSION} — онлайн проверка", DISCLAIMER, ""]
    for idx, item in enumerate(rows[:8], 1):
        evidence = collect_evidence(item["claim"], item["topic"])
        verdict, verdict_score, explanation = evaluate_evidence(evidence)
        ev_html = []
        ev_copy = []
        for ev_idx, ev in enumerate(evidence, 1):
            cls = "evidence-link manual" if ev.get("manual") else "evidence-link"
            ev_html.append(
                f'<a class="{cls}" href="{escape(ev["url"])}" target="_blank">'
                f'<b>{ev_idx}. {escape(ev.get("source", "източник"))}</b><span>{escape(ev.get("title", "линк"))}</span>'
                f'<small>{escape(ev.get("snippet", ""))}</small></a>'
            )
            ev_copy.append(f'{ev_idx}. {ev.get("source", "източник")}: {ev.get("title", "линк")} — {ev.get("url", "")}' )
        cards.append(f'''
<div class="claim-card evidence-card">
  <div class="claim-top">
    <span class="claim-index">LIVE #{idx:02}</span>
    <span class="topic-pill">{escape(item["topic"])}</span>
    <span class="label-pill">{escape(verdict)}</span>
  </div>
  <div class="claim-text">{escape(item["claim"])}</div>
  <div class="meter"><span style="width:{verdict_score}%"></span></div>
  <div class="meta-line"><b>Индикативна оценка:</b> {escape(verdict)} · {escape(explanation)}</div>
  <div class="evidence-list">{"".join(ev_html)}</div>
  <div class="caution">Това не е финална присъда. Отвори линковете и сравни твърдението с първичните данни.</div>
</div>
''')
        copy_lines.append(f"{idx}. {item['claim']}")
        copy_lines.append(f"Оценка: {verdict} | {explanation}")
        copy_lines.extend(ev_copy)
        copy_lines.append("")
    cards.append("</div>")
    return "\n".join(cards), "\n".join(copy_lines)


def analyze(text):
    rows = analyze_claims(text)
    html, copy_text = render_results(rows)
    return html, copy_text, f"Открити твърдения: {len(rows)}"


def real_check(text):
    rows = analyze_claims(text)
    html, copy_text = render_real_check(rows)
    return html, copy_text, f"Онлайн проверени твърдения: {min(len(rows), 8)}"


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


def transcribe(file_path):
    if not file_path:
        return "", None, "Качи аудио или видео файл."
    path = getattr(file_path, "name", file_path)
    size = file_size_mb(path)
    if size > MAX_MEDIA_MB:
        return "", None, f"Файлът е {size:.1f} MB. За публичното демо лимитът е {MAX_MEDIA_MB} MB. Качи по-кратък файл."
    model = get_model()
    segments, _ = model.transcribe(path, language="bg", beam_size=5, vad_filter=True)
    segments = list(segments)
    transcript = " ".join(seg.text.strip() for seg in segments).strip()
    srt_blocks = []
    for i, seg in enumerate(segments, 1):
        srt_blocks.append(f"{i}\n{ts(seg.start)} --> {ts(seg.end)}\n{seg.text.strip()}\n")
    out = tempfile.NamedTemporaryFile(delete=False, suffix=".srt", mode="w", encoding="utf-8")
    out.write("\n".join(srt_blocks))
    out.close()
    return transcript, out.name, f"Готово. Дължина: {len(transcript)} символа. Модел: {MODEL_SIZE}/{DEVICE}/{COMPUTE_TYPE}"


def transcribe_and_analyze(file_path):
    transcript, srt_file, status = transcribe(file_path)
    html, copy_text, count = analyze(transcript)
    return transcript, html, copy_text, srt_file, status + " · " + count


def transcribe_and_real_check(file_path):
    transcript, srt_file, status = transcribe(file_path)
    html, copy_text, count = real_check(transcript)
    return transcript, html, copy_text, srt_file, status + " · " + count


def save_feedback(name, email, kind, comment):
    with open("feedback.txt", "a", encoding="utf-8") as f:
        f.write(f"Име: {name or '-'}\nИмейл: {email or '-'}\nТип: {kind}\nКоментар: {comment}\n---\n")
    return "Записано. Благодаря за обратната връзка."


CSS = """
:root {--neon-cyan:#22d3ee;--neon-purple:#a855f7;--neon-blue:#2563eb;}
.gradio-container{max-width:1220px!important;margin:auto!important;background:radial-gradient(circle at 10% 10%,rgba(34,211,238,.18),transparent 26%),radial-gradient(circle at 82% 16%,rgba(168,85,247,.20),transparent 24%),radial-gradient(circle at 50% 100%,rgba(37,99,235,.14),transparent 32%),#020617!important;}
body,.gradio-container{color:#e5e7eb!important;}
#neon-hero{position:relative;padding:34px;border-radius:28px;overflow:hidden;border:1px solid rgba(34,211,238,.28);background:linear-gradient(135deg,rgba(2,6,23,.95),rgba(30,27,75,.82));box-shadow:0 0 42px rgba(34,211,238,.16),inset 0 0 80px rgba(168,85,247,.10);}
#neon-hero:before{content:"";position:absolute;inset:0;background-image:linear-gradient(rgba(34,211,238,.09) 1px,transparent 1px),linear-gradient(90deg,rgba(34,211,238,.09) 1px,transparent 1px);background-size:36px 36px;mask-image:linear-gradient(to bottom,white,transparent);}
.hero-content{position:relative;z-index:2}.hero-kicker{color:var(--neon-cyan);letter-spacing:.22em;text-transform:uppercase;font-size:12px;font-weight:800}.hero-title{margin:10px 0 8px;font-size:clamp(34px,7vw,72px);line-height:.9;font-weight:950;color:white;text-shadow:0 0 24px rgba(34,211,238,.32)}.hero-subtitle{max-width:790px;color:#cbd5e1;font-size:18px}.stat-row{display:flex;flex-wrap:wrap;gap:12px;margin-top:24px}.stat-chip{border:1px solid rgba(168,85,247,.28);background:rgba(15,23,42,.62);border-radius:999px;padding:9px 14px;color:#e0f2fe}.gr-button-primary{background:linear-gradient(90deg,#0891b2,#7c3aed)!important;border:0!important;box-shadow:0 0 22px rgba(34,211,238,.22)!important}.results-grid{display:grid;gap:16px}.claim-card{border:1px solid rgba(34,211,238,.22);background:linear-gradient(135deg,rgba(15,23,42,.82),rgba(30,41,59,.62));border-radius:22px;padding:18px;box-shadow:0 0 26px rgba(34,211,238,.08)}.evidence-card{border-color:rgba(168,85,247,.35);box-shadow:0 0 30px rgba(168,85,247,.12)}.claim-top{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:12px}.claim-index{color:#67e8f9;font-family:ui-monospace,monospace;font-weight:900}.topic-pill,.label-pill,.source-chip{display:inline-flex;border-radius:999px;padding:6px 10px;font-size:12px;text-decoration:none}.topic-pill{background:rgba(37,99,235,.18);color:#bfdbfe;border:1px solid rgba(59,130,246,.25)}.label-pill{background:rgba(168,85,247,.18);color:#e9d5ff;border:1px solid rgba(168,85,247,.28)}.claim-text{font-size:16px;color:#f8fafc;line-height:1.55}.meter{height:7px;border-radius:999px;background:rgba(148,163,184,.17);overflow:hidden;margin:14px 0 8px}.meter span{display:block;height:100%;background:linear-gradient(90deg,#22d3ee,#a855f7);border-radius:999px}.meta-line{color:#cbd5e1;font-size:13px;margin-bottom:12px}.sources-row{display:flex;flex-wrap:wrap;gap:8px}.source-chip{color:#cffafe!important;border:1px solid rgba(34,211,238,.24);background:rgba(8,145,178,.12)}.evidence-list{display:grid;gap:10px;margin-top:12px}.evidence-link{display:grid;gap:4px;text-decoration:none!important;color:#e0f2fe!important;border:1px solid rgba(34,211,238,.22);background:rgba(2,6,23,.36);border-radius:16px;padding:12px}.evidence-link span{color:#fff}.evidence-link small{color:#94a3b8;line-height:1.35}.evidence-link.manual{border-style:dashed;color:#fde68a!important}.caution{margin-top:12px;color:#fbbf24;font-size:12px}.empty-state{border:1px dashed rgba(148,163,184,.35);border-radius:20px;padding:24px;color:#cbd5e1;background:rgba(15,23,42,.5)}.footer-note{color:#94a3b8;font-size:13px}
"""

HERO = f"""
<div id="neon-hero"><div class="hero-content">
<div class="hero-kicker">PUBLIC CLAIM INTELLIGENCE · BULGARIA · v{APP_VERSION}</div>
<div class="hero-title">ClaimRadar BG</div>
<div class="hero-subtitle">Футуристичен тестов панел за откриване и реална първична проверка на публични твърдения. Системата маркира твърденията, търси следи в надеждни източници и оставя финалната оценка на човека.</div>
<div class="stat-row"><span class="stat-chip">Текст → твърдения</span><span class="stat-chip">Онлайн източници</span><span class="stat-chip">Аудио/видео → SRT</span><span class="stat-chip">Без окончателни присъди</span></div>
</div></div>
"""

with gr.Blocks(title=APP_TITLE, theme=gr.themes.Soft(primary_hue="cyan", neutral_hue="slate"), css=CSS) as demo:
    gr.HTML(HERO)
    gr.Markdown(f"<p class='footer-note'>{DISCLAIMER}</p>")

    with gr.Tab("🚦 Проверка на текст"):
        with gr.Row():
            file = gr.File(label="Качи .txt", file_types=[".txt"])
            status = gr.Textbox(label="Статус", value="Готов за анализ.", interactive=False)
        text = gr.Textbox(label="Текст / транскрипт", lines=12, placeholder="Постави текст от дебат, интервю, реч, новина или парламентарна стенограма...")
        file.change(load_txt, file, text)
        with gr.Row():
            btn = gr.Button("Провери твърденията", variant="primary")
            real_btn = gr.Button("Реална проверка с източници")
            gr.ClearButton([text], value="Изчисти")
        result_html = gr.HTML(label="Резултати")
        copy_box = gr.Textbox(label="Копирай резултатите", lines=10, show_copy_button=True)
        btn.click(analyze, text, [result_html, copy_box, status])
        real_btn.click(real_check, text, [result_html, copy_box, status])

    with gr.Tab("🔎 Реална проверка"):
        gr.Markdown("Този режим опитва онлайн търсене в официални и надеждни източници. Работи най-добре с 1–8 конкретни твърдения.")
        real_text = gr.Textbox(label="Твърдения за проверка", lines=10, placeholder="Пример: Инфлацията в България беше ...")
        check_live = gr.Button("Провери онлайн", variant="primary")
        live_status = gr.Textbox(label="Статус", value="Готов за онлайн проверка.", interactive=False)
        live_html = gr.HTML(label="Онлайн резултати")
        live_copy = gr.Textbox(label="Копирай проверката", lines=10, show_copy_button=True)
        check_live.click(real_check, real_text, [live_html, live_copy, live_status])

    with gr.Tab("🎙️ Аудио/видео"):
        gr.Markdown(f"Качи кратък файл за публичен тест. Препоръчителен лимит: до **{MAX_MEDIA_MB} MB**.")
        media = gr.File(label="Аудио или видео", file_types=[".mp3", ".wav", ".m4a", ".mp4", ".webm", ".ogg", ".flac", ".aac"])
        with gr.Row():
            tr_btn = gr.Button("Само транскрибирай")
            full_btn = gr.Button("Транскрибирай и провери", variant="primary")
            real_media_btn = gr.Button("Транскрибирай и провери онлайн")
        transcript = gr.Textbox(label="Транскрипция", lines=12, show_copy_button=True)
        media_results = gr.HTML(label="Резултати")
        media_copy = gr.Textbox(label="Копирай резултатите", lines=8, show_copy_button=True)
        srt_file = gr.File(label="Свали .SRT")
        media_status = gr.Textbox(label="Статус", interactive=False)
        tr_btn.click(transcribe, media, [transcript, srt_file, media_status])
        full_btn.click(transcribe_and_analyze, media, [transcript, media_results, media_copy, srt_file, media_status])
        real_media_btn.click(transcribe_and_real_check, media, [transcript, media_results, media_copy, srt_file, media_status])

    with gr.Tab("🛰️ Източници"):
        source_md = "## Източници по категории\n\n"
        for topic, names in TOPIC_SOURCES.items():
            links = " · ".join([f"[{name}]({SOURCE_LINKS[name]})" for name in names])
            source_md += f"### {topic}\n{links}\n\n"
        source_md += "\nПърво се проверяват официални първични данни. Медии и fact-check сайтове се използват като допълнителен контекст."
        gr.Markdown(source_md)

    with gr.Tab("🧬 Как работи"):
        gr.HTML("""
<div class="claim-card"><div class="claim-text"><b>Pipeline v0.3:</b> текст/транскрипт → откриване на твърдения → категоризация → онлайн търсене по източници → линкове/сигнали → човешка проверка</div><div class="meter"><span style="width:86%"></span></div><div class="meta-line">Следваща версия: AI оценка с цитати, запазване на проверки и публичен share link.</div></div>
""")

    with gr.Tab("📡 Обратна връзка"):
        name = gr.Textbox(label="Име по избор")
        email = gr.Textbox(label="Имейл по избор")
        kind = gr.Dropdown(label="Тип проблем", choices=["грешна категоризация", "липсващ източник", "проблем с интерфейса", "идея за функция", "друго"], value="идея за функция")
        comment = gr.Textbox(label="Коментар", lines=5)
        send = gr.Button("Изпрати", variant="primary")
        feedback_status = gr.Textbox(label="Статус")
        send.click(save_feedback, [name, email, kind, comment], feedback_status)

    gr.Markdown(f"---\n{DISCLAIMER}")

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)

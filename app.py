import os
import re
import tempfile
from pathlib import Path
from html import escape

import gradio as gr
from faster_whisper import WhisperModel

APP_TITLE = "ClaimRadar BG"
APP_VERSION = "0.2"
DISCLAIMER = "Тестов инструмент: резултатите са ориентир за проверка, не окончателна правна, политическа или журналистическа оценка."
MAX_MEDIA_MB = int(os.getenv("MAX_MEDIA_MB", "80"))
MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "base")
DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
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


def analyze(text):
    rows = analyze_claims(text)
    html, copy_text = render_results(rows)
    return html, copy_text, f"Открити твърдения: {len(rows)}"


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
.hero-content{position:relative;z-index:2}.hero-kicker{color:var(--neon-cyan);letter-spacing:.22em;text-transform:uppercase;font-size:12px;font-weight:800}.hero-title{margin:10px 0 8px;font-size:clamp(34px,7vw,72px);line-height:.9;font-weight:950;color:white;text-shadow:0 0 24px rgba(34,211,238,.32)}.hero-subtitle{max-width:760px;color:#cbd5e1;font-size:18px}.stat-row{display:flex;flex-wrap:wrap;gap:12px;margin-top:24px}.stat-chip{border:1px solid rgba(168,85,247,.28);background:rgba(15,23,42,.62);border-radius:999px;padding:9px 14px;color:#e0f2fe}.gr-button-primary{background:linear-gradient(90deg,#0891b2,#7c3aed)!important;border:0!important;box-shadow:0 0 22px rgba(34,211,238,.22)!important}.results-grid{display:grid;gap:16px}.claim-card{border:1px solid rgba(34,211,238,.22);background:linear-gradient(135deg,rgba(15,23,42,.82),rgba(30,41,59,.62));border-radius:22px;padding:18px;box-shadow:0 0 26px rgba(34,211,238,.08)}.claim-top{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:12px}.claim-index{color:#67e8f9;font-family:ui-monospace,monospace;font-weight:900}.topic-pill,.label-pill,.source-chip{display:inline-flex;border-radius:999px;padding:6px 10px;font-size:12px;text-decoration:none}.topic-pill{background:rgba(37,99,235,.18);color:#bfdbfe;border:1px solid rgba(59,130,246,.25)}.label-pill{background:rgba(168,85,247,.18);color:#e9d5ff;border:1px solid rgba(168,85,247,.28)}.claim-text{font-size:16px;color:#f8fafc;line-height:1.55}.meter{height:7px;border-radius:999px;background:rgba(148,163,184,.17);overflow:hidden;margin:14px 0 8px}.meter span{display:block;height:100%;background:linear-gradient(90deg,#22d3ee,#a855f7);border-radius:999px}.meta-line{color:#cbd5e1;font-size:13px;margin-bottom:12px}.sources-row{display:flex;flex-wrap:wrap;gap:8px}.source-chip{color:#cffafe!important;border:1px solid rgba(34,211,238,.24);background:rgba(8,145,178,.12)}.caution{margin-top:12px;color:#fbbf24;font-size:12px}.empty-state{border:1px dashed rgba(148,163,184,.35);border-radius:20px;padding:24px;color:#cbd5e1;background:rgba(15,23,42,.5)}.footer-note{color:#94a3b8;font-size:13px}
"""

HERO = f"""
<div id="neon-hero"><div class="hero-content">
<div class="hero-kicker">PUBLIC CLAIM INTELLIGENCE · BULGARIA · v{APP_VERSION}</div>
<div class="hero-title">ClaimRadar BG</div>
<div class="hero-subtitle">Футуристичен тестов панел за откриване на проверими твърдения в български текст, аудио и видео. Системата маркира твърденията, предлага източници и оставя финалната проверка на човека.</div>
<div class="stat-row"><span class="stat-chip">Текст → твърдения</span><span class="stat-chip">Аудио/видео → SRT</span><span class="stat-chip">Български източници</span><span class="stat-chip">Без окончателни присъди</span></div>
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
            gr.ClearButton([text], value="Изчисти")
        result_html = gr.HTML(label="Резултати")
        copy_box = gr.Textbox(label="Копирай резултатите", lines=10, show_copy_button=True)
        btn.click(analyze, text, [result_html, copy_box, status])

    with gr.Tab("🎙️ Аудио/видео"):
        gr.Markdown(f"Качи кратък файл за публичен тест. Препоръчителен лимит: до **{MAX_MEDIA_MB} MB**.")
        media = gr.File(label="Аудио или видео", file_types=[".mp3", ".wav", ".m4a", ".mp4", ".webm", ".ogg", ".flac", ".aac"])
        with gr.Row():
            tr_btn = gr.Button("Само транскрибирай")
            full_btn = gr.Button("Транскрибирай и провери", variant="primary")
        transcript = gr.Textbox(label="Транскрипция", lines=12, show_copy_button=True)
        media_results = gr.HTML(label="Резултати")
        media_copy = gr.Textbox(label="Копирай резултатите", lines=8, show_copy_button=True)
        srt_file = gr.File(label="Свали .SRT")
        media_status = gr.Textbox(label="Статус", interactive=False)
        tr_btn.click(transcribe, media, [transcript, srt_file, media_status])
        full_btn.click(transcribe_and_analyze, media, [transcript, media_results, media_copy, srt_file, media_status])

    with gr.Tab("🛰️ Източници"):
        source_md = "## Източници по категории\n\n"
        for topic, names in TOPIC_SOURCES.items():
            links = " · ".join([f"[{name}]({SOURCE_LINKS[name]})" for name in names])
            source_md += f"### {topic}\n{links}\n\n"
        source_md += "\nПърво се проверяват официални първични данни. Медии и fact-check сайтове се използват като допълнителен контекст."
        gr.Markdown(source_md)

    with gr.Tab("🧬 Как работи"):
        gr.HTML("""
<div class="claim-card"><div class="claim-text"><b>Pipeline:</b> текст/транскрипт → откриване на твърдения → категоризация → препоръчани източници → човешка проверка</div><div class="meter"><span style="width:78%"></span></div><div class="meta-line">Следваща версия: автоматично web търсене, AI оценка с цитати и публичен share link.</div></div>
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

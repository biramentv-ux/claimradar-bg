import os
import re
import tempfile
from pathlib import Path

import gradio as gr
from faster_whisper import WhisperModel

DISCLAIMER = "Това е тестов инструмент. Резултатите не са окончателна оценка и трябва да се проверяват по източници."
MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "base")
DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
_model = None

SOURCES = {
    "икономика": ["НСИ", "БНБ", "Евростат"],
    "инфлация": ["НСИ", "Евростат", "БНБ"],
    "пенсии": ["НОИ", "НСИ"],
    "данъци": ["НАП", "Министерство на финансите"],
    "избори": ["ЦИК", "Народно събрание"],
    "закони": ["Народно събрание", "Държавен вестник"],
    "бюджет": ["Министерство на финансите", "Народно събрание"],
    "здравеопазване": ["Министерство на здравеопазването", "НЗОК", "НСИ"],
    "образование": ["МОН", "НСИ"],
    "енергетика": ["Министерство на енергетиката", "КЕВР"],
    "ес": ["Евростат", "Европейска комисия"],
    "друго": ["Factcheck.bg", "БТА", "БНР", "НСИ"],
}

KEYWORDS = {
    "инфлация": ["инфлация", "цени", "поскъп", "ипц"],
    "пенсии": ["пенсия", "пенсии", "нои", "осигур"],
    "данъци": ["данък", "данъци", "ддс", "нап"],
    "избори": ["избор", "избори", "цик", "мандат"],
    "закони": ["закон", "парламент", "народно събрание"],
    "бюджет": ["бюджет", "дефицит", "дълг", "финанси"],
    "здравеопазване": ["здраве", "болница", "нзок", "лекар"],
    "образование": ["училище", "учител", "мон", "образование"],
    "енергетика": ["ток", "газ", "енерг", "кевр"],
    "ес": ["ес", "европа", "евростат", "шенген"],
    "икономика": ["бвп", "иконом", "безработ", "заплати", "доходи"],
}


def get_model():
    global _model
    if _model is None:
        _model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)
    return _model


def topic_for(sentence):
    text = sentence.lower()
    for topic, words in KEYWORDS.items():
        if any(word in text for word in words):
            return topic
    return "друго"


def split_text(text):
    return [c.strip() for c in re.split(r"(?<=[.!?])\s+|\n+", text or "") if len(c.strip()) > 20]


def analyze(text):
    rows = []
    for chunk in split_text(text)[:20]:
        low = chunk.lower()
        score = 20
        if re.search(r"\d", chunk):
            score += 35
        if any(x in low for x in ["%", "процент", "милиона", "милиарда", "лв", "евро"]):
            score += 20
        if any(x in low for x in ["повече", "по-малко", "увелич", "намал", "спрямо", "най-"]):
            score += 20
        topic = topic_for(chunk)
        if score >= 70:
            label = "вероятно проверимо"
        elif score >= 45:
            label = "за проверка"
        else:
            label = "нужни са източници"
        rows.append([chunk, topic, label, f"{min(score, 95)}%", ", ".join(SOURCES.get(topic, SOURCES["друго"]))])
    if not rows:
        return [], "Няма открити ясни проверими твърдения."
    return rows, DISCLAIMER


def ts(seconds):
    ms = int((seconds - int(seconds)) * 1000)
    total = int(seconds)
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def transcribe(file_path):
    if not file_path:
        return "", None
    model = get_model()
    segments, _ = model.transcribe(file_path, language="bg", beam_size=5, vad_filter=True)
    segments = list(segments)
    transcript = " ".join(seg.text.strip() for seg in segments).strip()
    srt = []
    for i, seg in enumerate(segments, 1):
        srt.append(f"{i}\n{ts(seg.start)} --> {ts(seg.end)}\n{seg.text.strip()}\n")
    out = tempfile.NamedTemporaryFile(delete=False, suffix=".srt", mode="w", encoding="utf-8")
    out.write("\n".join(srt))
    out.close()
    return transcript, out.name


def transcribe_and_analyze(file_path):
    transcript, srt_file = transcribe(file_path)
    rows, note = analyze(transcript)
    return transcript, rows, note, srt_file


def load_txt(file):
    if not file:
        return ""
    path = getattr(file, "name", file)
    try:
        return Path(path).read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return Path(path).read_text(encoding="cp1251", errors="ignore")


def save_feedback(name, email, kind, comment):
    with open("feedback.txt", "a", encoding="utf-8") as f:
        f.write(f"Име: {name or '-'}\nИмейл: {email or '-'}\nТип: {kind}\nКоментар: {comment}\n---\n")
    return "Благодаря. Обратната връзка е записана."

with gr.Blocks(title="BG Fact Checker", theme=gr.themes.Soft(primary_hue="indigo")) as demo:
    gr.Markdown("# BG Fact Checker\nПублична тестова версия за България: текст, аудио/видео транскрипция и откриване на проверими твърдения.\n\n" + DISCLAIMER)

    with gr.Tab("Проверка на текст"):
        file = gr.File(label="Качи .txt файл", file_types=[".txt"])
        text = gr.Textbox(label="Текст или транскрипт", lines=12)
        file.change(load_txt, file, text)
        btn = gr.Button("Провери твърденията", variant="primary")
        table = gr.Dataframe(headers=["Твърдение", "Тема", "Етикет", "Увереност", "Източници"])
        note = gr.Markdown()
        btn.click(analyze, text, [table, note])

    with gr.Tab("Аудио/видео"):
        media = gr.File(label="Качи аудио или видео", file_types=[".mp3", ".wav", ".m4a", ".mp4", ".webm", ".ogg", ".flac", ".aac"])
        with gr.Row():
            tr_btn = gr.Button("Само транскрибирай")
            full_btn = gr.Button("Транскрибирай и провери", variant="primary")
        transcript = gr.Textbox(label="Транскрипция", lines=12)
        table2 = gr.Dataframe(headers=["Твърдение", "Тема", "Етикет", "Увереност", "Източници"])
        note2 = gr.Markdown()
        srt_file = gr.File(label="Свали .SRT")
        tr_btn.click(transcribe, media, [transcript, srt_file])
        full_btn.click(transcribe_and_analyze, media, [transcript, table2, note2, srt_file])

    with gr.Tab("Източници"):
        gr.Markdown("## Източници\nНСИ, БНБ, НОИ, НАП, ЦИК, Народно събрание, Министерски съвет, Министерство на финансите, Евростат, Factcheck.bg, БТА и БНР.")

    with gr.Tab("Обратна връзка"):
        name = gr.Textbox(label="Име по избор")
        email = gr.Textbox(label="Имейл по избор")
        kind = gr.Dropdown(label="Тип проблем", choices=["грешна категоризация", "липсващ източник", "проблем с интерфейса", "идея за функция", "друго"], value="идея за функция")
        comment = gr.Textbox(label="Коментар", lines=5)
        send = gr.Button("Изпрати")
        status = gr.Textbox(label="Статус")
        send.click(save_feedback, [name, email, kind, comment], status)

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)

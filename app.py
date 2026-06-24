import re
import gradio as gr

DISCLAIMER = "Това е тестов инструмент. Резултатите не са окончателна оценка и трябва да се проверяват по източници."

SOURCES = {
    "икономика": ["НСИ", "БНБ", "Евростат"],
    "пенсии": ["НОИ", "НСИ"],
    "данъци": ["НАП", "Министерство на финансите"],
    "избори": ["ЦИК", "Народно събрание"],
    "закони": ["Народно събрание", "Държавен вестник"],
    "друго": ["Factcheck.bg", "БТА", "БНР", "НСИ"],
}

KEYWORDS = {
    "икономика": ["бвп", "иконом", "инфлация", "цени", "заплати", "безработ"],
    "пенсии": ["пенсия", "пенсии", "нои", "осигур"],
    "данъци": ["данък", "данъци", "ддс", "нап"],
    "избори": ["избор", "избори", "цик", "мандат"],
    "закони": ["закон", "парламент", "народно събрание"],
}


def topic_for(sentence):
    text = sentence.lower()
    for topic, words in KEYWORDS.items():
        if any(word in text for word in words):
            return topic
    return "друго"


def analyze(text):
    chunks = [c.strip() for c in re.split(r"(?<=[.!?])\s+|\n+", text or "") if len(c.strip()) > 20]
    rows = []
    for chunk in chunks[:20]:
        score = 20
        low = chunk.lower()
        if re.search(r"\d", chunk):
            score += 35
        if any(x in low for x in ["%", "процент", "милиона", "млрд", "лв", "евро"]):
            score += 20
        if any(x in low for x in ["повече", "по-малко", "увелич", "намал", "спрямо"]):
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


def load_txt(file):
    if not file:
        return ""
    with open(file.name, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()

with gr.Blocks(title="BG Fact Checker") as demo:
    gr.Markdown("# BG Fact Checker\nПублична тестова версия за откриване на проверими твърдения в български текст.")
    file = gr.File(label="Качи .txt файл", file_types=[".txt"])
    text = gr.Textbox(label="Текст или транскрипт", lines=12)
    file.change(load_txt, file, text)
    btn = gr.Button("Провери твърденията", variant="primary")
    table = gr.Dataframe(headers=["Твърдение", "Тема", "Етикет", "Увереност", "Източници"])
    note = gr.Markdown()
    btn.click(analyze, text, [table, note])

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)

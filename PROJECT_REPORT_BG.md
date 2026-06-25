# ClaimRadar BG — технически рапорт на създаденото

Дата: 2026-06-25
Проект: `biramentv-ux/claimradar-bg`
Публичен Space: `https://dyrakarmy-claimradar-bg.hf.space`

## 1. Общо описание

ClaimRadar BG е български prototype за откриване, транскрибиране, първична проверка и публично споделяне на проверими твърдения. Проектът комбинира Gradio интерфейс, FastAPI backend, WebSocket realtime слой, Faster Whisper транскрипция, AI verdict engine, Search API слой, публичен архив и browser extension.

Основната цел е потребителят да може да постави текст, да качи аудио/видео или да използва browser overlay върху YouTube/live страници, след което системата да извлече проверими твърдения, да предложи релевантни източници, да даде предпазлива оценка и да позволи споделяне чрез публична страница.

## 2. Основни компоненти

### 2.1 Gradio UI

Създаден е публичен интерфейс с няколко основни таба:

- текстова проверка;
- AI verdict;
- word realtime статус;
- аудио/видео транскрипция;
- публичен архив;
- източници;
- обратна връзка;
- admin панел.

Интерфейсът е в dark futuristic стил с animated/glassmorphism елементи.

### 2.2 FastAPI backend

FastAPI backend обслужва:

- `/health`;
- `/ws/realtime`;
- `/ws/transcribe`;
- `/check/<share_id>`;
- `/api/check/<share_id>`;
- `/search/status`;
- `/sources/whitelist`.

Backend-ът монтира Gradio приложението и добавя публични routes за result pages.

### 2.3 Hugging Face Docker deployment

Проектът е подготвен като Hugging Face Docker Space.

Създадени/настроени са:

- `Dockerfile`;
- `launch.py`;
- `README.md` metadata със `sdk: docker` и `app_port: 7860`;
- GitHub Actions sync към Hugging Face.

Целта е всяка промяна в GitHub `main` автоматично да се качва към Hugging Face Space.

### 2.4 GitHub Actions sync

Създаден е workflow:

```text
.github/workflows/sync-to-hf.yml
```

Workflow-ът:

- стартира при push към `main`;
- може да се стартира ръчно чрез `workflow_dispatch`;
- валидира Docker metadata;
- качва repo-то към Hugging Face Space;
- поддържа Hugging Face Trusted Publisher/OIDC;
- има fallback чрез `HF_TOKEN` secret.

## 3. Функции за проверка на текст

Системата анализира текст чрез локален claim detector:

- разделяне на изречения;
- оценка дали изречението е проверимо;
- търсене на числа, проценти, години, пари, сравнения и публични теми;
- класифициране по тема;
- confidence score;
- препоръчани източници.

Категории:

- икономика;
- инфлация;
- пенсии;
- данъци;
- избори;
- закони;
- бюджет;
- здравеопазване;
- образование;
- енергетика;
- ЕС;
- друго.

## 4. AI Verdict Engine

Добавена е версия `2.2-ai-verdict`.

Pipeline:

```text
claim → evidence search → AI сравнение → verdict → цитати
```

AI verdict връща:

- verdict;
- confidence;
- short reason;
- citations;
- missing context;
- engine status.

Възможни verdict-и:

- Вярно;
- По-скоро вярно;
- Частично вярно;
- Подвеждащо;
- Невярно;
- Непроверимо;
- Нужен контекст.

Системата има fallback режим, ако `OPENAI_API_KEY` не е зададен. В този случай приложението не пада, а използва rule-based verdict и продължава да показва evidence links.

## 5. Search API слой

Добавен е файл:

```text
search_providers.py
```

Поддържани search providers:

- Brave Search API;
- Bing Search API;
- Tavily;
- SerpAPI;
- Google Programmable Search / CSE;
- DuckDuckGo fallback.

Environment променливи:

```text
SEARCH_PROVIDER=auto
SEARCH_STRICT_WHITELIST=1
BRAVE_SEARCH_API_KEY
BING_SEARCH_API_KEY
TAVILY_API_KEY
SERPAPI_API_KEY
GOOGLE_SEARCH_API_KEY
GOOGLE_CSE_ID
```

Whitelist източници:

```text
nsi.bg
bnb.bg
nssi.bg
nra.bg
cik.bg
parliament.bg
dv.parliament.bg
minfin.bg
gov.bg
ec.europa.eu
factcheck.bg
bta.bg
bnr.bg
```

По подразбиране strict whitelist е включен.

## 6. Аудио/видео транскрипция

Добавена е поддръжка за качване на аудио/видео и транскрипция чрез Faster Whisper.

Поддържани формати:

- `.mp3`;
- `.wav`;
- `.m4a`;
- `.mp4`;
- `.webm`;
- `.ogg`;
- `.flac`;
- `.aac`.

Функции:

- само транскрибиране;
- транскрибиране + проверка;
- транскрибиране + online check;
- транскрибиране + AI verdict;
- `.srt` export;
- запазване на резултат в публичен архив.

## 7. Realtime WebSocket слой

Добавени endpoints:

```text
/ws/realtime
/ws/transcribe
```

WebSocket слой приема audio chunks, транскрибира rolling buffer и връща:

- partial transcript;
- new words;
- word stream;
- claims;
- status;
- elapsed time.

Realtime е prototype режим. На free CPU Hugging Face Space може да има забавяне.

## 8. Публичен архив и Share ID

Създаден е публичен архив със Share ID.

Потребителят може да:

- запази проверка;
- получи Share ID;
- зареди проверка по ID;
- експортира JSON;
- отвори публична страница.

Публичен формат:

```text
/check/<share_id>
```

JSON формат:

```text
/api/check/<share_id>
```

Важно ограничение: текущо архивът е JSONL файл в локалната файлова система на Space-а. На free Hugging Face Space записите може да се загубят при рестарт. За production е нужна persistent база, например Supabase/PostgreSQL.

## 9. Публична продуктова страница

Добавя се route:

```text
/product
```

Тази страница служи като потребителско обяснение на продукта:

- какво е ClaimRadar BG;
- за кого е предназначен;
- как работи;
- какви режими има;
- какво означават verdict-ите;
- как се използват източниците;
- какви са ограниченията;
- какви са следващите стъпки.

## 10. Browser extension

Създаден е Chrome/Edge extension:

```text
extension/
```

Основни файлове:

- `manifest.json`;
- `popup.html`;
- `popup.js`;
- `content.js`;
- `audio_controls.js`;
- `service_worker.js`;
- `offscreen.html`;
- `offscreen.js`;
- `README.md`.

Добавени функции във версия `2.2.0`:

- overlay ON/OFF;
- Captions / Audio / Selection режими;
- Floating mini mode;
- auto-start в YouTube;
- auto-open transcript hint;
- copy claim;
- copy all;
- send to app;
- report;
- local history;
- realtime audio controls;
- live word stream;
- live claim cards.

## 11. Admin панел

Admin панелът показва:

- брой запазени проверки;
- feedback записи;
- realtime статус;
- AI engine статус;
- последни проверки;
- feedback поток.

За защита се използва:

```text
ADMIN_KEY
```

Ако `ADMIN_KEY` не е зададен, admin панелът остава заключен.

## 12. Environment variables

Препоръчителни стойности за Hugging Face:

```text
WHISPER_MODEL_SIZE=base
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
MAX_MEDIA_MB=80
REALTIME_INTERVAL=2.5
ROLLING_WINDOW_MB=12
STREAM_MAX_BUFFER_MB=60
STREAM_LANGUAGE=bg
PUBLIC_BASE_URL=https://dyrakarmy-claimradar-bg.hf.space
SEARCH_PROVIDER=auto
SEARCH_STRICT_WHITELIST=1
```

Secrets по избор:

```text
OPENAI_API_KEY
BRAVE_SEARCH_API_KEY
BING_SEARCH_API_KEY
TAVILY_API_KEY
SERPAPI_API_KEY
GOOGLE_SEARCH_API_KEY
GOOGLE_CSE_ID
ADMIN_KEY
HF_TOKEN
```

## 13. Важни ограничения

Текущият проект е public beta prototype.

Ограничения:

- не е финална журналистическа/правна проверка;
- AI verdict зависи от качеството на evidence;
- free CPU transcription може да е бавна;
- JSONL архивът не е production база;
- search API keys още не са добавени;
- няма user accounts;
- няма production rate limiting;
- няма permanent audit database;
- няма diarization;
- няма напълно production-ready browser store packaging.

## 14. Препоръчани следващи стъпки

### Преди миграция към друг сървър

1. Добавяне на всички API keys като secrets.
2. Тестване на `/health`, `/search/status`, `/sources/whitelist`.
3. Запазване на няколко тестови проверки.
4. Тестване на `/check/<share_id>` и `/api/check/<share_id>`.
5. Тестване на extension-а в Chrome/Edge.
6. Проверка на audio transcription с кратки файлове.

### За production миграция

1. Supabase/PostgreSQL за persistent storage.
2. Rate limiting.
3. Queue/background jobs за тежки transcriptions.
4. GPU или отделна speech-to-text услуга.
5. Authentication за admin.
6. Domain + HTTPS.
7. Monitoring/logging.
8. Browser extension packaging.
9. Privacy policy и terms page.
10. Dataset/audit trail за проверките.

## 15. Заключение

До този момент е създадена пълна основа за ClaimRadar BG като public beta продукт: web app, AI verdict engine, search layer, browser extension, realtime audio prototype, public result pages, archive, admin panel и автоматичен GitHub → Hugging Face deployment.

Проектът вече е подходящ за демонстрации, ранни тестове и подготовка за миграция към по-сериозна инфраструктура.

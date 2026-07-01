# ClaimRadar BG Overlay Extension v2.3

Chrome/Edge extension prototype за live Bulgarian public-claim detection с polished overlay, captions/audio режими, local history, packaging script и Hugging Face realtime backend.

## Какво прави

- добавя футуристичен overlay върху страницата;
- има toggle за включване/изключване от popup;
- има избор на режим: **Captions / Audio / Selection**;
- има **Floating mini mode**;
- стартира автоматично в YouTube, ако е позволено;
- опитва автоматично да отвори YouTube transcript panel;
- чете видими YouTube captions и transcript сегменти;
- анализира маркиран текст от всяка страница;
- открива вероятно проверими твърдения чрез локални JS heuristics;
- показва бързи линкове за търсене в официални/надеждни източници;
- има **Copy claim** и **Copy all**;
- има **Send to app** за отваряне на ClaimRadar BG с избраното твърдение;
- има **Report** бутон, който копира report payload и го пази в local history;
- пази local history в browser storage;
- поддържа tab audio capture към WebSocket backend;
- показва live word stream и live claim cards от streaming backend.

## Packaging

Extension package се прави със стандартен Python script без външни зависимости:

```bash
python scripts/package_extension.py
```

Скриптът:

- генерира PNG icons в `extension/icons/`;
- валидира задължителните файлове;
- проверява icons в `manifest.json`;
- създава ZIP в `dist/`.

Изходният файл е:

```text
dist/claimradar-bg-extension-v2.3.0.zip
```

## GitHub Actions artifact

Workflow:

```text
.github/workflows/build-extension.yml
```

Той се стартира при промени в `extension/**`, packaging script-а или ръчно от Actions → **Build Extension Package**.

След успешен run ZIP файлът се взима от Artifacts:

```text
claimradar-bg-extension
```

## Store readiness файлове

Добавени са:

```text
extension/PRIVACY_POLICY.md
extension/STORE_LISTING_BG.md
```

`PRIVACY_POLICY.md` описва какви данни extension-ът обработва, какво се пази локално и кога се праща към backend.

`STORE_LISTING_BG.md` съдържа draft описание, permissions explanation и списък със screenshots, които трябва да се подготвят преди Chrome Web Store / Edge Add-ons submission.

## Инсталация локално

1. Свали repo-то като ZIP или clone:

```bash
git clone https://github.com/biramentv-ux/claimradar-bg.git
```

2. Отвори Chrome или Edge.
3. Отвори:

```text
chrome://extensions
```

или:

```text
edge://extensions
```

4. Включи **Developer mode**.
5. Натисни **Load unpacked**.
6. Избери папката:

```text
claimradar-bg/extension
```

7. След всяка промяна в extension файловете натисни **Reload** на extension-а в `chrome://extensions`.
8. Отвори YouTube видео с captions/transcript или маркирай текст на произволна страница.

## Audio режим

1. Избери `Audio realtime` в popup-а или натисни **Realtime** в overlay-а.
2. Extension-ът иска tab audio stream чрез `chrome.tabCapture`.
3. Offscreen document стартира `MediaRecorder`.
4. Аудиото се изпраща на chunks към WebSocket backend.
5. Backend-ът транскрибира `.webm` buffer чрез Faster Whisper.
6. Overlay-ът показва live word stream + claim cards.

## Ограничения

Това е prototype. На free CPU Hugging Face Space realtime audio може да има забавяне. За стабилен production режим е нужен GPU Space, VPS или отделна managed speech-to-text услуга.

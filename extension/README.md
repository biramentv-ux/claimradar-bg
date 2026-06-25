# ClaimRadar BG Overlay Extension v1.0

Chrome/Edge extension prototype for live Bulgarian public-claim detection.

## Какво прави

- добавя автоматичен футуристичен overlay върху страницата;
- стартира автоматично в YouTube;
- чете видими YouTube captions и transcript сегменти, когато са налични;
- може да анализира маркиран текст от всяка страница;
- открива вероятно проверими твърдения чрез локални JS heuristics;
- категоризира твърденията по теми;
- показва бързи линкове за търсене в официални/надеждни източници;
- отваря публичното приложение ClaimRadar BG.

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

7. Отвори YouTube видео с включени captions или transcript.
8. Overlay-ът трябва да се появи долу вдясно.

## Ограничения

Това е prototype. Не прихваща директно аудио поток. Работи с видим текст, captions, transcript сегменти или селекция от страницата. За истински live audio fact-check следващият етап е browser audio capture + speech-to-text backend.

## Следваща стъпка

- Chrome offscreen audio capture;
- streaming speech-to-text;
- API връзка към ClaimRadar BG backend;
- автоматична AI оценка с цитирани линкове;
- overlay върху live debate stream.

# ClaimRadar BG — Easy Remote Access

Графичен режим за много лесен достъп извън Wi‑Fi.

## Цел

Потребителят да не пише команди. Отваря `/remote-simple`, натиска голям бутон и получава линк за телефона.

## Routes

```text
/remote-simple
/api/remote-simple/status
/api/remote-simple/start
/api/remote-simple/stop
/api/remote-simple/help
```

## Как работи

### Cloudflare Quick Tunnel

Ако `cloudflared` е инсталиран, бутонът **Старт — най-лесно** стартира:

```bash
cloudflared tunnel --url http://127.0.0.1:8765
```

След като `cloudflared` върне `trycloudflare.com` адрес, UI-то показва:

```text
https://....trycloudflare.com/mobile
```

### ngrok fallback

Ако потребителят предпочита ngrok и е инсталиран:

```bash
ngrok http 8765
```

UI-то разпознава публичния HTTPS URL и го показва като `/mobile` линк.

## За деца / начинаещи

UI-то е с три големи действия:

```text
🟢 Старт — най-лесно
📋 Копирай линка
🔴 Стоп
```

## Важно за сигурността

Публичният tunnel изкарва локалния app към интернет. Затова mobile remote flow остава с PIN pairing:

```text
/mobile/pair
/mobile
```

За production употреба е по-добре да се използва Cloudflare remotely-managed tunnel, Cloudflare Access, ngrok auth policy или друг допълнителен защитен слой.

## Variables

```bash
REMOTE_SIMPLE_ENABLED=1
REMOTE_SIMPLE_DEFAULT_PROVIDER=cloudflare
REMOTE_CLOUDFLARED_PATH=C:\\tools\\cloudflared.exe
REMOTE_NGROK_PATH=C:\\tools\\ngrok.exe
APP_PORT=8765
```

## Проверка

```bash
curl http://127.0.0.1:8765/api/remote-simple/status
```

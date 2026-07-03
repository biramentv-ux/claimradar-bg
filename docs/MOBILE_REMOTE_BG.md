# ClaimRadar BG — Phone Remote Mode

Този режим позволява телефонът да се използва като дистанционно за локалния desktop app. Компютърът трябва да е включен и ClaimRadar BG Desktop backend-ът трябва да работи.

## Routes

```text
/mobile
/mobile/pair
/api/mobile/status
/api/mobile/pair
/api/mobile/analyze
/api/mobile/archive/import-text
```

## Как работи

1. Desktop app стартира локалния backend на порт `8765`.
2. При `MOBILE_REMOTE_BIND_LAN=1` backend-ът слуша на `0.0.0.0`, за да бъде видим в LAN/Wi‑Fi мрежата.
3. Компютърът показва pairing страница:

```text
http://127.0.0.1:8765/mobile/pair
```

4. Телефонът отваря LAN URL, например:

```text
http://192.168.1.50:8765/mobile
```

5. Потребителят въвежда PIN от екрана на компютъра.
6. Телефонът получава временен session token и може да изпраща текст за анализ към PC-то.

## Desktop variables

```bash
MOBILE_REMOTE_ENABLED=1
MOBILE_REMOTE_REQUIRE_PIN=1
MOBILE_REMOTE_BIND_LAN=1
MOBILE_REMOTE_SESSION_TTL_SECONDS=86400
APP_PORT=8765
```

## Защитен модел

- PIN се показва на PC pairing страницата.
- Телефонът не изпълнява AI локално — само изпраща заявка.
- PC backend-ът изпълнява Ollama/faster-whisper/local archive.
- Session token се пази в browser localStorage на телефона.
- За LAN достъп трябва защитена домашна/частна мрежа.

## Извън домашната мрежа

За достъп извън LAN може да се използва tunnel, например Cloudflare Tunnel или ngrok. Това трябва да се комбинира с PIN pairing и допълнителни access controls при production употреба.

Примерна посока:

```bash
cloudflared tunnel --url http://127.0.0.1:8765
ngrok http 8765
```

## Проверка

```bash
curl http://127.0.0.1:8765/api/mobile/status
```

Отвори на PC:

```text
http://127.0.0.1:8765/mobile/pair
```

После отвори на телефона един от LAN URL адресите, показани на pairing страницата.

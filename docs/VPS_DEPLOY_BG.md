# ClaimRadar BG на собствен VPS (Docker + Caddy HTTPS)

Алтернатива на Hugging Face Space: приложението и Caddy (автоматичен Let's Encrypt HTTPS) вървят с Docker Compose на твой сървър.

## Изисквания

- VPS с **Ubuntu 22.04/24.04 или Debian 12**, минимум **2 GB RAM** (скриптът добавя 2 GB swap при по-малко от ~3.5 GB), 20 GB диск.
- SSH достъп като `root` (или потребител със `sudo`).
- Достъп до DNS на `dyrakarmy.eu` (SuperHosting).

## Безплатен VPS: Oracle Cloud Always Free

- Shape **VM.Standard.A1.Flex** (ARM, Ubuntu 24.04): до **2 OCPU / 12 GB RAM** безплатно (от юни 2026, преди 4/24). Нужна е карта за верификация.
- В VCN → Security List добави Ingress правила за TCP **80** и **443** от `0.0.0.0/0`. Вътрешните iptables правила на Oracle образа `install.sh` ги отваря сам.
- При „Out of host capacity“ опитай друг Availability Domain или по-късно.
- SSH като `ubuntu` (не root): `ssh ubuntu@<IP> "curl -fsSL .../install.sh | sudo bash"`.

## 1. DNS (SuperHosting)

Добави **A запис**: `claimradar` → `<IP на VPS-а>`, TTL 3600.
Ако вече има `CNAME claimradar → hf.space`, изтрий го — двата записа не могат да съществуват едновременно.

## 2. Инсталация — една команда

От Windows PowerShell (вграденият OpenSSH клиент):

```powershell
ssh root@<IP> "curl -fsSL https://raw.githubusercontent.com/biramentv-ux/claimradar-bg/main/deploy/vps/install.sh | bash"
```

Или директно на сървъра:

```bash
curl -fsSL https://raw.githubusercontent.com/biramentv-ux/claimradar-bg/main/deploy/vps/install.sh | sudo bash
```

С OpenAI ключ и Supabase (по желание):

```bash
curl -fsSL https://raw.githubusercontent.com/biramentv-ux/claimradar-bg/main/deploy/vps/install.sh | sudo OPENAI_API_KEY=sk-... DATABASE_URL=postgresql://... bash
```

Скриптът: инсталира Docker, добавя swap при малко RAM, клонира репото в `/opt/claimradar-bg`, създава `.env` с генерирани ключове (mode 600), отваря 80/443 в `ufw`, проверява DNS, build-ва и стартира, изчаква `/health`.

## 3. Обновяване

Пусни същата команда отново — прави `git pull` и rebuild, `.env` и данните се запазват (Docker volumes `claimradar_data`, `model_cache`, `caddy_data`).

## Полезни команди (на сървъра)

```bash
cd /opt/claimradar-bg
grep -E '^(OWNER|ADMIN)_KEY' .env                                   # admin ключове
docker compose -f deploy/vps/docker-compose.yml logs -f app           # логове
docker compose -f deploy/vps/docker-compose.yml restart app           # рестарт
nano .env && docker compose -f deploy/vps/docker-compose.yml --env-file .env up -d   # промяна на настройки
```

## Сигурност

- Навън са отворени само 80/443 (Caddy). Портът на приложението (7860) не се публикува.
- Caddy заменя подадения от клиента `X-Forwarded-For` с реалния IP, така че rate limiting не може да се заобиколи.
- Desktop функциите (тунели, мобилно управление, локални модели) са изключени (`DESKTOP_FEATURES_ENABLED=0`).

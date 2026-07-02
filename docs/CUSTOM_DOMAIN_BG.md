# ClaimRadar BG — Custom Domain: dyrakarmy.eu

Този документ описва как да вържеш ClaimRadar BG към собствен домейн.

## Препоръчителен адрес

Най-сигурният вариант за Hugging Face Spaces е subdomain:

```text
claimradar.dyrakarmy.eu
```

Причината е, че Hugging Face Spaces custom domain setup изисква CNAME към:

```text
hf.space
```

При root/apex домейн като `dyrakarmy.eu` някои DNS панели не позволяват CNAME на самия root. Ако SuperHosting не поддържа ALIAS/ANAME/CNAME flattening за root домейн, използвай subdomain.

## DNS запис в SuperHosting

В DNS зоната на `dyrakarmy.eu` добави:

```text
Type:  CNAME
Host:  claimradar
Name:  claimradar.dyrakarmy.eu
Value: hf.space
TTL:   3600
```

Не използвай „Насочване към IP адрес“, защото Hugging Face не дава стабилен IP за Spaces custom domain. Нужно е CNAME.

## Hugging Face Space settings

Влез в Hugging Face Space:

```text
https://huggingface.co/spaces/dyrakarmy/claimradar-bg/settings
```

После:

```text
Settings → Custom Domain → claimradar.dyrakarmy.eu
```

След добавяне статусът първо ще бъде pending. След DNS propagation трябва да стане ready.

## Hugging Face Variables

Добави или промени Variables:

```bash
PUBLIC_BASE_URL=https://claimradar.dyrakarmy.eu
CUSTOM_DOMAIN=claimradar.dyrakarmy.eu
ROOT_DOMAIN=dyrakarmy.eu
HF_SPACE_URL=https://dyrakarmy-claimradar-bg.hf.space
```

## Проверка в приложението

След redeploy провери:

```text
https://claimradar.dyrakarmy.eu/custom-domain/status
https://claimradar.dyrakarmy.eu/health
https://claimradar.dyrakarmy.eu/product
```

Fallback URL:

```text
https://dyrakarmy-claimradar-bg.hf.space/custom-domain/status
```

## GitHub Actions проверка

Workflow:

```text
.github/workflows/custom-domain-check.yml
```

Стартира се от:

```text
GitHub → Actions → Custom Domain Check → Run workflow
```

Artifact:

```text
claimradar-bg-custom-domain-report
```

Съдържа:

```text
custom-domain-report.json
custom-domain-report.md
```

## Локална проверка

```bash
python scripts/check_custom_domain.py \
  --domain claimradar.dyrakarmy.eu \
  --hf-url https://dyrakarmy-claimradar-bg.hf.space
```

## Ако искаш root домейн `dyrakarmy.eu`

Пробвай само ако DNS панелът предлага ALIAS/ANAME/CNAME flattening:

```text
Type:  ALIAS / ANAME / Flattened CNAME
Host:  @
Value: hf.space
```

Ако панелът позволява само IP address redirect, не го използвай за Hugging Face Spaces. Използвай subdomain `claimradar.dyrakarmy.eu`.

## DNS propagation

Промените обикновено отнемат от няколко минути до 48 часа. В твоя DNS панел е посочено, че DNS промените влизат в сила от 2 до 48 часа.

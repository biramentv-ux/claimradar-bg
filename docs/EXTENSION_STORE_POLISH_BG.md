# ClaimRadar BG — Extension Store Polish

Този документ обобщава Chrome Web Store / Microsoft Edge Add-ons подготовката за extension-а.

## Какво е подготвено

```text
extension/STORE_LISTING_BG.md
extension/PRIVACY_POLICY.md
extension/STORE_PRIVACY_DECLARATION_BG.md
scripts/generate_extension_store_assets.py
tests/test_extension_store_polish.py
```

## Permission minimization

Manifest v2.4.0 премахва `<all_urls>` от `content_scripts.matches`.

Default content script injection остава само за YouTube:

```text
https://www.youtube.com/*
https://*.youtube.com/*
```

За други сайтове се използва:

```text
activeTab + scripting
```

Това позволява overlay injection само след user action от popup-а.

## Default host permissions

```text
https://www.youtube.com/*
https://*.youtube.com/*
https://dyrakarmy-claimradar-bg.hf.space/*
```

## Optional host permissions

```text
https://*.hf.space/*
http://127.0.0.1/*
http://localhost/*
```

Те са за custom backend / local development и не се изискват като default store permissions.

## Store screenshots и promo assets

Генериране:

```bash
python scripts/generate_extension_store_assets.py
```

Output:

```text
extension/store_assets/generated/chrome_screenshot_1_popup_640x400.png
extension/store_assets/generated/chrome_screenshot_2_youtube_overlay_640x400.png
extension/store_assets/generated/chrome_screenshot_3_claim_cards_640x400.png
extension/store_assets/generated/chrome_screenshot_4_audio_mode_640x400.png
extension/store_assets/generated/chrome_screenshot_5_product_page_640x400.png
extension/store_assets/generated/chrome_small_promo_440x280.png
extension/store_assets/generated/chrome_marquee_promo_1400x560.png
```

## Privacy copy

Store privacy declaration е в:

```text
extension/STORE_PRIVACY_DECLARATION_BG.md
```

Основни твърдения:

- user data is not sold;
- no microphone capture;
- no password/payment/private message collection;
- no remote hosted code execution;
- local history stays in browser storage;
- backend send happens only when the relevant user feature is used.

## Store package

```bash
python scripts/package_extension.py
```

Output:

```text
dist/claimradar-bg-extension-v2.4.0.zip
```

## Review test flow

1. Install unpacked extension.
2. Open YouTube with Bulgarian captions/transcript.
3. Use Captions / Transcript mode.
4. Test overlay claim cards.
5. Test selected text on a normal HTTPS page by clicking `Inject overlay в текущия tab`.
6. Test audio mode only after explicit user start.
7. Confirm local history can be cleared.

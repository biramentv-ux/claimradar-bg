# ClaimRadar BG Overlay — Privacy Policy

Last updated: 2026-06-25

## Summary

ClaimRadar BG Overlay is a browser extension prototype for Bulgarian claim detection, transcript analysis, and optional realtime tab-audio transcription through the configured ClaimRadar BG backend.

The extension is designed to process only the content needed for the user-started analysis mode.

## Data the extension may process

Depending on user settings, the extension may process:

- selected page text;
- visible YouTube captions or transcript text;
- visible page text used for local claim detection;
- tab audio chunks when the user starts realtime audio mode;
- local history entries saved in the browser;
- report payloads when the user presses Report.

## Data stored locally

The extension stores settings and local history in Chrome/Edge extension storage:

- enabled/disabled state;
- input mode;
- backend URL;
- mini mode settings;
- recent local analysis history;
- recent report entries.

The local history remains in the user's browser until the user clears it from the popup or removes the extension.

## Data sent to backend

The extension may send data to the configured backend only when the relevant feature is used:

- realtime audio chunks to the WebSocket backend;
- transcript or claim text when using send/report actions;
- report details when the user reports a result.

Default backend:

```text
wss://dyrakarmy-claimradar-bg.hf.space/ws/realtime
```

and:

```text
https://dyrakarmy-claimradar-bg.hf.space
```

## Permissions

The extension uses:

- `activeTab` to interact with the current tab after user action;
- `storage` to save local settings/history;
- `tabCapture` for user-started tab audio capture;
- `offscreen` to run audio recording through an offscreen document;
- host permissions for YouTube, configured backend domains, localhost and Hugging Face Spaces.

## What the extension does not do

The extension does not sell user data.

The extension does not intentionally collect passwords, payment data, private messages, or browser history.

The extension does not capture microphone audio directly. Audio realtime mode captures the active tab audio only after user action.

## Limitations

ClaimRadar BG is a prototype and should not be treated as a final legal, political, or journalistic authority. Always verify results through the evidence links and official sources.

## Contact

For project information, visit the product page:

```text
https://dyrakarmy-claimradar-bg.hf.space/product
```

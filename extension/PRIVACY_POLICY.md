# ClaimRadar BG Overlay — Privacy Policy

Last updated: 2026-07-02

## Summary

ClaimRadar BG Overlay is a browser extension for Bulgarian claim detection, YouTube transcript analysis, selected-text review and optional realtime active-tab audio transcription through the configured ClaimRadar BG backend.

The extension is designed to process only the content needed for the user-selected analysis mode.

## Data the extension may process

Depending on user settings and user actions, the extension may process:

- selected page text;
- visible YouTube captions or transcript text;
- visible page text used for local claim detection;
- active tab audio chunks only when the user starts realtime audio mode;
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

- selected text, captions/transcript text or page text when the user starts analysis or sends content to the app;
- active-tab audio chunks when the user starts realtime audio mode;
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
- `scripting` to inject the overlay into the active tab after user action;
- `storage` to save local settings/history;
- `tabCapture` for user-started active-tab audio capture;
- `offscreen` to run audio recording through an offscreen document;
- default host permissions for YouTube and the ClaimRadar BG production backend;
- optional host permissions for custom Hugging Face or localhost development backends.

## What the extension does not do

The extension does not sell user data.

The extension does not intentionally collect passwords, payment data, private messages, full browser history, cookies or keystrokes.

The extension does not capture microphone audio directly. Realtime mode captures active tab audio only after user action.

The extension does not automatically run on every website after installation. Outside YouTube pages, the overlay is injected into the active tab only after the user opens the popup and applies it.

## Data retention

Local settings and history are stored in the user's browser. The user can clear local history from the popup or remove the extension to delete extension storage.

Backend processing and retention depends on the configured ClaimRadar BG backend. The public prototype includes its own privacy and terms pages.

## Limitations

ClaimRadar BG is a prototype and should not be treated as a final legal, political or journalistic authority. Always verify results through the evidence links and official sources.

## Contact

For project information, visit the product page:

```text
https://dyrakarmy-claimradar-bg.hf.space/product
```

# ClaimRadar BG Overlay — Store Listing Draft

## Short description

Bulgarian claim detection overlay with YouTube captions, selection analysis and optional realtime tab-audio transcription.

## Full description

ClaimRadar BG Overlay helps users identify potentially checkable claims in Bulgarian public content.

It can analyze selected text, visible page text, YouTube captions/transcripts and, when started by the user, active tab audio through a realtime backend.

Main features:

- ClaimRadar overlay on web pages;
- YouTube captions/transcript analysis;
- selected text analysis;
- optional realtime tab-audio transcription;
- live word stream from backend;
- local claim cards with confidence score;
- quick evidence search links;
- copy claim / copy all;
- send to ClaimRadar BG app;
- report button;
- local history;
- floating mini mode.

## Category suggestion

Productivity or News & Weather.

## Permissions explanation

### activeTab

Used to apply the overlay to the current page after the user opens or uses the extension.

### storage

Used to store local settings and local analysis history.

### tabCapture

Used only when the user starts realtime audio mode. Captures active tab audio, not microphone audio.

### offscreen

Used to run the MediaRecorder process for tab audio capture.

### host permissions

Used for YouTube caption/transcript analysis, backend communication, local development and Hugging Face-hosted ClaimRadar BG endpoints.

## Review notes

This is a prototype tool. Results are not final legal, political or journalistic conclusions. Users should verify claims through the evidence links and official sources.

## Required screenshots before submission

Prepare screenshots for:

1. Popup settings panel.
2. Overlay active on a YouTube video.
3. Claim cards with evidence links.
4. Realtime audio mode.
5. Product page at `/product`.

## Privacy policy URL

Use the public product/privacy page when available, or include the text from `extension/PRIVACY_POLICY.md` during review.

# ClaimRadar BG Overlay — Store Privacy Declaration

Use this as the basis for Chrome Web Store / Edge Add-ons privacy fields.

## Single purpose

ClaimRadar BG Overlay identifies potentially checkable Bulgarian-language claims from user-selected text, visible YouTube captions/transcripts, visible page text and optional user-started active-tab audio, then helps the user send those claims to ClaimRadar BG for analysis and evidence review.

## Data categories

### Personally identifiable information

Not intentionally collected.

### Health information

Not intentionally collected.

### Financial and payment information

Not collected.

### Authentication information

Not collected. The extension does not ask for passwords, tokens or login credentials.

### Personal communications

Not intentionally collected. The extension is intended for public page text, selected text, YouTube transcripts/captions and active-tab audio when started by the user.

### Location

Not collected.

### Web history

Not collected as browsing history. The extension may process the current active page content only for the selected feature.

### Website content

Processed only when the user uses selected-text/page-text mode, YouTube captions/transcript mode or starts realtime tab-audio mode.

### User activity

Local settings and local analysis history are stored in the user's browser.

## Data sale / transfer

User data is not sold.

The extension sends content only to the configured ClaimRadar BG backend when the user uses a feature that requires backend processing.

## Remote code

The extension does not execute remote hosted code. Backend responses are treated as data for display in the extension UI.

## Permission minimization

The extension uses `activeTab` + `scripting` for manual active-tab overlay injection outside YouTube. It uses YouTube host permissions for automatic transcript workflow and the production backend host permission for ClaimRadar BG communication. Localhost/custom Hugging Face host access is optional.

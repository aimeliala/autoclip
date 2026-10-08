# AutoClip Studio — Changelog

## v0.2.1 (2026-10-09) — Subtitle 429 resilience

- `yt-dlp` remains required. YouTube metadata, public heatmap (if available),
  and authorized video retrieval remain part of the product.
- Removed automatic subtitle downloads from the video download operation.
  Subtitle errors no longer invalidate a successfully downloaded video.
- Independent, best-effort subtitle fetch requests only one relevant track:
  creator-provided captions when possible, otherwise an original-language
  automatic track when known. Automatic translations are not requested.
- HTTP 429 is now logged as a subtitle-only failure with a local, one-hour
  subtitle request cooldown; the app does not rotate identities or evade rate limits.
- Fallback: cached subtitle/transcript -> Groq or faster-whisper (according
  to settings) -> ranking from heatmap/chapters/timeline without captions.
- Added regression tests for independent video download, subtitle language
  selection, HTTP 429 cooldown and fallback pipeline.

Note: No live YouTube requests or native macOS GUI tests could be executed in
this build environment. Install the project dependencies on your own Mac.

# 0088 — Voice reads locally through the browser's speech engine

- **Status:** accepted
- **Date:** 2026-11-02
- **Anchors:** `frontend/src/lib/listen.js` (controller + `buildSpeechText`), `frontend/src/components/ListenButton.jsx`, `frontend/src/components/ListenDock.jsx` (mounted once by `AppShell`); smoke check "profile sections read aloud through the listen dock"
- **Shapes:** the same read in two places — App Profile groups and History's plan context — through one controller, so a third surface is a builder, not a second player

## Context

The App Profile detail page is the most text-heavy surface in the studio —
researched paragraphs, feature lists, claim statements — and reading it is the
founder's main chore before a render. History's plan context is the same kind
of eyes-busy, read-once material.

Two engines were real alternatives. Browser `speechSynthesis` exists on every
target browser, costs nothing, needs no network and no key, and never sends
the profile text anywhere. A hosted TTS provider (OpenAI / ElevenLabs) offers
noticeably better voices but adds a backend endpoint, per-character cost,
first-play latency, and a privacy surface — the researched profile is the
founder's own product data, and there is no reason to ship it out to be read.

## Decision

- Voice uses the browser's own engine. No backend, no key, no text leaves the
  device; the controls simply do not render where the API is missing.
- Speech text is built from the data model (labels and values), never scraped
  from the DOM — chrome, glyphs and test ids cannot end up in the audio.
- One shared controller in `lib/listen.js`: one voice at a time, nothing
  autoplays, and `AppShell` owns the single dock (pause, stop, 0.75–1.5× rate,
  persisted). Sections carry only a start/stop toggle.
- A hosted-voice upgrade, if the host voices prove too coarse, arrives as a
  Stage-2 `POST /api/tts` (R2-cached, signed URLs) behind the same module.

## Alternatives rejected

- **Server TTS now.** Cost, latency and a privacy surface for a read-out of
  the founder's own research, before any usage evidence that the host voices
  are not good enough. Parked, not forbidden: the module boundary is the
  integration point.
- **Reading the rendered DOM.** Text scraped from the page speaks button
  labels, counts and whatever a state branch happens to render; data-driven
  sentences stay correct under every loading and error state.
- **Autoplay on page open.** A voice that starts itself is a hijacked tab;
  speech starts on a click and stops the moment the founder says so.

## Consequences

- Voice quality varies by OS (better on macOS / Windows 11 than older
  Android); acceptable for product copy, and the rate control is the escape
  hatch.
- The dock is the only new fixed chrome; it unmounts on settle and on error,
  so a stopped voice leaves no residue on the page.
- The smoke suite stubs a speech engine to pin the flow; where no engine
  exists the controls hide, so no other check is affected.

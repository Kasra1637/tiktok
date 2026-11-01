# Live render sample (consented, manual)

Mocked checks prove the gates refuse correctly. Only a real provider response
proves today's prompt produces a real hook-then-middle clip with the
photograph surviving as the presenter.

## Rules

- Never in CI. Never on someone else's key.
- Requires `ALLOW_LIVE_SAMPLE=1` plus a funded `OPENROUTER_API_KEY` from the
  environment. The key is never printed, stored, or committed.
- One render at a time. Watch the clip yourself and fill the dated checklist
  in `test_reports/live-sample-YYYY-MM-DD.md` by hand.
- Historical reports do not prove today's provider or revision is working.
  Re-sample after prompt, model, or provider changes.

## Run

```bash
ALLOW_LIVE_SAMPLE=1 OPENROUTER_API_KEY=<key> python backend/live_sample.py \
  --photo ./my-face.png --out ./live-clips --profile <profile-id> --project <project-id>
```

Then submit one render through the studio, save the clip under the out dir,
and complete the checklist: end-to-end playback, identity likeness, no
generated demo/CTA, and the claim-check outcome with its next step.

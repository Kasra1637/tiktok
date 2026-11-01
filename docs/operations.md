# Operations and recovery

This runbook describes the existing FastAPI + CRA deployment. It is not an
authorization to deploy, repair live data, rotate credentials, or spend provider
credits. Begin with [setup](../README.md#quick-start) and
[architecture](architecture.md).

## Before any intervention

- Record the symptom, generation/project ID, active image/revision, timestamp
  and sanitized error. Never copy tokens, private env files, signed playback
  links or personal session fixtures into a report.
- Identify the active database and where media are saved before a restart.
  Back up local DB/media and resolve pending replica writes before replacing
  an ephemeral instance. Do not delete storage as a troubleshooting step.
- Distinguish **provider job state**, **durable-save state**, **browser polling
  state**, and **post-kit state**. They are independent; a paused browser check
  or failed caption is not proof a render failed.
- Prefer the existing targeted retry over a new paid render. Do not retry a
  provider refusal blindly or switch the model without an explicit choice.

## Health and observations

| Signal | Meaning and next action |
|---|---|
| `GET /api/` responds | Basic API reachability only; says nothing about DB/media durability. |
| `GET /api/health` | Authenticated inventory. Read `database`, `durable`, `your_rows`; table-read failures may be reported inside an HTTP 200 response. |
| `database: turso` | This process established a cloud-backed connection. Also inspect logs for sync failures: recent unsynced writes can remain only on the local replica. |
| `database: local-ephemeral-fallback` | Turso failed and writes are going locally. Treat as a persistence incident even if the UI works. |
| `database: local-sqlite`, `durable: false` | Local development default, unsafe for durable production state on an ephemeral host. A laptop's local file is not deleted merely by restarting Python. |
| `GET /api/metrics` | Authenticated process-local counters/uptime. Not a persistent monitoring history or provider billing meter. |
| `GET /docs` | FastAPI's current route/schema reference; do not rely on stale endpoint lists in chat. |

Use an existing authenticated browser session for private health reads or your
normal secure HTTP client. Do not log session tokens to demonstrate access.

## Troubleshooting

### Missing profile/history after restart

1. Read health and startup logs; determine active backend, not only configured
   `TURSO_DATABASE_URL`.
2. Verify the deployment has both Turso variable names configured and can reach
   the database. Do not print their values.
3. If the instance has accepted local writes, preserve the local file/replica
   before restart. The cloud copy can be intact while the UI is reading a
   different, empty local store.
4. Resolve the connection and reconcile any local-only writes deliberately.
   There is no automatic conflict-free merge runbook or backup guarantee.

Local SQLite defaults to `backend/storage/hookforge.db`. The libsql embedded
replica uses `hookforge.db` relative to the backend process working directory.
These are not interchangeable copies. Back up the active store using a
consistent SQLite/Turso backup procedure, not an arbitrary file copy while
writes are active. Test restoration on a disposable copy before an incident.

### Auth missing, sign-in disabled, or 401

- Client: `REACT_APP_CLERK_PUBLISHABLE_KEY` must exist at **build time**. A
  runtime variable cannot repair an already-built CRA bundle; rebuild it.
- Server: `CLERK_JWKS_URL` must be present **before imports**. The local launch
  command in the README loads the env file early. Restart after edits.
- Both keys must belong to the same Clerk configuration and the deployed
  origin must be allowed there. A redirect alone is not a tested login flow.
- Set `ENVIRONMENT=production` for hosted non-Render processes. The current
  boot guard recognizes Render markers or explicit production settings, not
  every hosting platform automatically.
- Without auth, local callers all use `anonymous`. Never enable that mode to
  work around a production authentication error.

### Development API calls return 404 / wrong-origin errors

Set the client backend URL to the actual API origin and restart the dev server.
Without it, development API requests hit CRA itself. In a single-origin
production bundle the empty URL is correct. For split origins, configure the
exact browser origin in `CORS_ORIGINS`; an empty value means `*`, not deny-all.

### Provider refuses the prompt or returns 429

- Keep the quoted provider error and next-step instructions visible. Review
  claim findings, identity requirements, camera conflicts and model limits.
- Provider 429 is throttling, not a successful submit. Polling can wait; a
  failed submit needs the explicit retry described by the app.
- Correct unsupported claims rather than disguising them. No phrase filter,
  claim checker or model setting guarantees acceptance or TikTok approval.
- Check the selected model/allowlist and
  [capability rules](../backend/video_providers.py), not only the public
  provider catalog. Do not add a fallback or a second render path.
- Live model verification spends credits. Use
  [verify_chat_model.py](../backend/verify_chat_model.py) and
  [verify_live_renders.py](../backend/verify_live_renders.py) only after
  explicit authorization. The render probe does not cover every model.

### Completed job, missing clip, or `storage_error`

1. In History, use the existing **storage retry** for a finished render before
   submitting another video. This reuses available media; it is not a new render.
2. Confirm R2's four required variable names are configured. A storage locator
   or provider URL is not itself proof of browser-readable durable media.
3. Preserve local MP4s while provider content links are still usable. Provider
   links may need server authorization and can expire.
4. For operator batch diagnosis, the existing script supports a read-only
   preview (it may contact provider sources):

   ```bash
   python backend/repair_failed_saves.py --dry-run --limit 10 --user USER_ID
   ```

   It loads the configured environment and targets that database. `--no-probe`
   avoids source network probes but cannot establish recoverability. `--db`
   selects a local SQLite file **only when Turso is not active**; do not assume
   it overrides cloud configuration. Inspect the script and active store first.
   Running it without `--dry-run` writes rows and uploads media; obtain explicit
   permission. Do not include private URLs from its output in public evidence.
5. If no complete local copy or usable remote source remains, say that recovery
   is unavailable. Do not label a newly generated replacement as the old clip.

### Browser stops checking a pending job

History bounds polling per row, names stops/errors and offers Check again.
Reload/check the generation rather than declaring it failed from a browser
state. A startup sweep can reconcile stranded jobs, but it is not an external,
durable queue and it cannot guarantee survival of every interruption.

### Demo + CTA draft or export failure

- The editing document is stored on the current browser/device, separately
  from the backend plan. Clearing site storage or changing devices can lose it.
  Preserve/export work before doing either.
- Check storage-quota errors and codec/device support. A smoke harness with
  media stubs is not proof that a device can encode the requested MP4.
- Preview and export share video-time drawing, but real playback, audio,
  transitions, likeness and text still require output inspection.
- A missing ffmpeg/ffprobe breaks server media work and real-encode tests;
  verify tools on the server PATH rather than suppressing those failures.

## Existing deployment path

```text
push to main
  -> .github/workflows/deploy.yml (serialized)
  -> Cloud Build / cloudbuild.yaml
  -> Dockerfile: CRA build + Python runtime
  -> Artifact Registry image tagged by commit
  -> image-only Cloud Run deployment
```

[Backend CI](../.github/workflows/ci.yml) runs separately on relevant backend
changes. It is **not** a dependency of the
[deploy workflow](../.github/workflows/deploy.yml). Frontend checks run locally.
Do not describe a push as CI-gated deployment. Only the configured workflow
path exclusions skip deployment; README/contributor-file edits are not currently
included in that exclusion list.

[cloudbuild.yaml](../cloudbuild.yaml) changes the image while retaining existing
service settings. Keep the workflow as the single deploy trigger; a second
provider-side Git trigger can race it. Never replace the entire secret list
with a partial `--set-secrets` or copy a local ignored service snapshot into
version control. Store private values in the host's secret manager and review
variable **names**, not values, when diagnosing configuration loss.

### Preflight and current caveats

- Review local affected checks and production config before an authorized
  publish. Back up schema/data and preserve local-only media/replica writes.
- The Docker runtime currently uses Python 3.11 while backend CI uses 3.12.
- The current Dockerfile tries to hash
  `/app/frontend/build/asset-manifest.json` in the runtime stage **before** that
  build is copied into the runtime filesystem. A strict CRA build does not
  test this container instruction; treat the container build as unverified
  until this path/order is repaired and a real Docker build succeeds.
- The Docker dependency step falls back from frozen Yarn install to ordinary
  install. It is not equivalent to a successful lockfile-only build.
- Embedded-replica boot sync and process-local in-flight guards assume a single
  process/instance view. Raising workers/instances requires coordination and
  freshness work, not just more CPU.
- Request-spawned media/background tasks require CPU after the response and
  can still be interrupted by an instance stop. Do not promise a durable queue.

These are documented constraints, not changes made by this refactor. Do not
claim production is verified from a local frontend build or unit suite.

### Authorized deployment verification

After a publish, verify the active revision/image matches the intended commit,
then check the actual hosted origin: HTML/JS/CSS, signed-in data isolation,
health durability, signed playback/download, and the affected workflow. A paid
render requires separate authorization. Record what was not tested.

### Rollback

Use the existing hosting controls to return traffic to a known-good revision
or deploy its known-good image **only when authorized**. Preserve current env
and secret bindings. An image rollback does not reverse startup migrations,
restore lost objects, reconcile unsynced replica writes, or rescue an expired
provider link. Check schema compatibility and active backend before directing
traffic, then verify health and the affected read/write/media paths again.

## Documentation maintenance

When commands or ownership move, update [README](../README.md),
[architecture](architecture.md), [CONTRIBUTING](../CONTRIBUTING.md) and the
relevant ADR together. Keep sanitized dated evidence in
[test_reports](../test_reports/) and scratch logs untracked. Do not overwrite
historical test failures with a claim they never occurred.

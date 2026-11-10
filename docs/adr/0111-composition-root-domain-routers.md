# 0111 — Composition-root decomposition into domain routers

Status: accepted

## Context

`server.py` carried the HTTP layer, the SQLite/Turso primitives, the schema
bootstrap, the brand/profile/template routes, the studio project/plan/strategy
routes, and the whole render pipeline in one ~10,600-line module. Reading or
testing any one concern booted all of them. ADR 0079 isolated deterministic
policy and studio panels but explicitly rejected a "directory-wide
router/database rewrite" as too risky, deferring it until a safe seam existed.

Two properties made the deferred rewrite risky. First, the test fixtures
redirect live state by rebinding module attributes on `server` at runtime
(`server.DB_PATH`, `server.TURSO_*`, `server._ACTIVE_BACKEND`,
`server._TURSO_BOOT_SYNC_DONE`). Second, the integration tests monkeypatch
behaviour with `monkeypatch.setattr(api, "<name>", ...)` where `api is server`.
Any extraction that captured a helper by value at import time would silently
miss both — the tests would still pass against the wrong object, or fail
confusingly.

## Decision

Give each domain one owner module and keep `server.py` as thin composition:
it includes each router and re-exports the helpers the remaining code and the
tests still call from `server`.

- `db.py` owns the SQLite/Turso primitives; `schema.py` owns schema creation
  and migrations. `db.py` reads the mutable config (`DB_PATH`, `TURSO_*`, the
  active backend, the boot-sync flag) through a `_server` back-reference set at
  import, because the test fixtures rebind those names on `server`.
- `routers/brands.py`, `routers/studio.py`, `routers/assets.py` own their
  endpoints. Each is configured once with the composition root
  (`configure_x(server_module)`) and resolves server-owned, test-patched names
  at call time through a module-local `_cfg(name)` lookup.
- No domain module imports `server`, in either direction. An unconfigured call
  raises `RuntimeError` instead of half-working.
- The move is move-only: no route path, response shape, status code or
  default changes. Extracted names are re-exported under their old names, so
  every existing caller and test keeps its binding.

`_submit_generation` stays the sole render submit path, in `server.py`.

## Alternatives rejected

- Injecting helper *values* at configure time (as `routers/post_kit.py` does):
  correct for stable deps, wrong for the names the tests monkeypatch, which
  must be looked up on `server` per call.
- Importing `server` from the routers: circular, and it boots the whole app to
  import a route module — the coupling this removes.
- Leaving `server.py` monolithic: keeps every concern in one read/test path.

## Consequences and evidence anchors

- `server.py` drops from ~10,640 to ~3,815 lines; each domain is independently
  importable and testable on ordinary data.
- Ownership identity (each re-export is the router's object) and the no-back-import
  rule are enforced in `backend/test_architecture.py`.
- `_cfg` failure is loud: calling a route before `configure_x` raises, never
  silently returns a stale default.
- The render pipeline, media/durable-storage glue and `ai_service.py` remain
  large; this decision bounds the HTTP/composition seam, not those.
- ADR 0079 stays in force; this record supplies the seam it deferred.

Anchors: `backend/db.py:_server`, `backend/routers/studio.py:_cfg`,
`backend/routers/assets.py:configure_assets`, `backend/server.py:configure_studio`,
`backend/test_architecture.py:test_studio_router_is_owned_by_routers_studio`.

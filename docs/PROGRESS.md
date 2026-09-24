# PROGRESS

Changelog per phase. One phase per session (CLAUDE.md "Phase discipline").

---

## Phase 0 — Scaffold (2026-09-24)

Project skeleton only: no models, no video, no events. Everything a later phase
plugs into exists and is tested; nothing pretends to work that does not.

### Backend (`backend/`)

- `app/main.py` — FastAPI app with a lifespan that wires, in order: JSON logging →
  settings → DB engine (+ `create_all` for first run) → `LocalStorageProvider` →
  device resolution → `ModelRegistry` (with the idle-unload reaper started). CORS
  for `http://localhost:3000`. No torch/transformers import anywhere in the import path.
- `app/core/config.py` — `Settings` (pydantic-settings) with **every** key from
  SPEC §21, typed, with defaults and validators for `QUALITY_WEIGHTS` /
  `DETECTOR_CLASSES`. `backend/.env.example` mirrors it.
- `app/core/logging.py` — one JSON object per line; the SPEC §22 trace fields
  (`camera_id, stage, model_id, model_version, device, inference_ms, n_detections,
  plan_id, event_id, vlm_latency_ms, vlm_answer, quality_components, final_decision`)
  are promoted to top level when passed via `extra`. `backend/log_config.json`
  routes uvicorn's own loggers through the same formatter, so *every* line is JSON.
- `app/core/device.py` — resolves `auto|cpu|cuda`, logs the decision and reason,
  WARNING when cuda is requested but unavailable (no silent fallback).
- `app/core/model_registry.py` — `register/get/unload/status`, lazy load-once,
  records load time + device + model_id + model_version, idle-unload background
  thread using `MODEL_IDLE_UNLOAD_SECONDS`, and `LOW_MEMORY_MODE` mutual-exclusion
  groups (loading a group member evicts the other resident member).
- `app/providers/base.py` — every ABC and data class from SPEC §5 (`Detection`,
  `TrackedObject`, `EventPackage`, `VLMVerdict`, `ParseResult` with
  `blockers`/`warnings`, `ParserContext`, …) plus `ModelUnavailableError` carrying
  an install hint.
- `app/providers/storage/local.py` — `LocalStorageProvider` rooted at `DATA_DIR`
  with the SPEC §19 prefixes, path-traversal guarded. The only class that touches
  the data filesystem.
- `app/db/` — SQLAlchemy 2.0 models for **all 23 tables** in SPEC §18, portable
  `JSON` columns, no SQLite-only features. Alembic initialised;
  `b78dae7f01c2_phase_0_initial_schema.py` creates all 23 (upgrade/downgrade
  round-trip verified).
- `app/schemas/dsl.py` — the Monitoring DSL from SPEC §8 with per-condition-type
  parameter validators (zone conditions need a zone; `near`/`far` need a numeric
  distance *and* units; `moving`/`speed_above` need speed units; `semantic` needs an
  action; binary conditions need an `object`, unary ones reject it; aliases must
  resolve; `logic` is `all`-only in v1).
- `app/api/` — implemented: `GET /api/health` (device, DB, storage, registry
  contents and per-feature availability with fix commands), `GET /api/metrics`
  (RSS, system RAM, CPU, GPU — torch imported lazily inside the function),
  `GET /api/setup-status`, `GET/PATCH /api/settings`. Every other SPEC §20 endpoint
  is registered as a **501** stub naming the phase that implements it, so the API
  surface is visible in `/docs` and nothing returns fake data.
- Runtime overrides: `settings_overrides` table merged over `.env`; `PATCH` validates
  against the `Settings` types, rejects unknown keys (400) and invalid values (422),
  and supports `reset` back to the `.env` value. `CORS_ORIGINS` is deliberately not
  runtime-tunable (it needs a restart).

### Frontend (`frontend/`)

Vite + React 18 + TypeScript (strict) + Tailwind 3. React Router with **exactly
three pages** and a top nav: Prompt `/`, Events `/events`, Settings `/settings`.
`src/services/api.ts` is a typed fetch wrapper (base URL from `VITE_API_URL`,
default `http://localhost:8000`) that turns a dead backend into a readable message
rather than an unhandled rejection.

- **Settings** — Setup checklist at the top (green/red per item, each unmet item
  showing its exact fix command with a copy button), then collapsible sections with
  anchors `#cameras #zones #calibration #anchors #concepts #models #thresholds
  #learning`. Sections open themselves when the URL hash points at them, ready for
  the Phase 4 "Set now" deep links. `#thresholds` is **functional** now (grouped
  detection / events / evidence / quality, per-key Save and "Reset to .env",
  override-vs-env source badge). `#models` shows live feature availability from
  `/api/health`. The rest say "Available after Phase N" — no fake content.
- **Prompt / Events** — titles and honest empty states that name the phase each
  feature arrives in. The natural-language box is visible but disabled.

### Tests

`pytest -q` → **87 passed in ~1.8 s**. `ruff check` and `ruff format --check` clean.
Coverage: config + overrides (persistence, reset, unknown/invalid keys), the DSL
(valid plans incl. the SPEC §8 forklift example, and a failing case for every
condition-parameter rule), `LocalStorageProvider` (round-trip, nested keys, missing
file, idempotent delete, path traversal), health/metrics/root/openapi + the 501
stubs, setup-status (endpoint shape plus each probe individually, with network and
webcam mocked), the model registry (lazy load-once, status fields, unload,
LOW_MEMORY_MODE eviction, idle reaping, failure recording) and device resolution,
and the JSON log formatter (all SPEC §22 fields, no internals leaked).

### Fix after the first acceptance run (2026-09-24)

**`alembic upgrade head` failed on a fresh clone** with
`sqlite3.OperationalError: unable to open database file`.

Root cause: `init_engine()` creates the SQLite file's parent directory before
connecting, but `alembic/env.py` builds its own engine via `engine_from_config`
and bypassed that helper. On a fresh clone `backend/data/` does not exist yet and
SQLite will not create a missing directory. The backend itself started fine,
because `create_all()` at startup goes through `init_engine` — which masked the
bug and meant only the documented setup sequence hit it.

Fix: `_ensure_sqlite_dir` is now public `ensure_sqlite_dir`, and `alembic/env.py`
calls it before setting the URL. `tests/unit/test_migrations.py` covers it —
verified to fail with the original `OperationalError` when the call is removed,
and the full `cp .env.example .env && alembic upgrade head` sequence was re-run
against a clean tree with no `data/` directory.

### Dependencies added (CLAUDE.md rule #13)

| Dependency | Reason |
|---|---|
| fastapi, uvicorn[standard] | the API server the spec calls for |
| pydantic, pydantic-settings | model/IO validation and typed config (rules #6, #7) |
| SQLAlchemy 2.0, alembic | SPEC §18 requires SQLAlchemy 2 + Alembic |
| httpx | probing Ollama's `/api/tags`; also the FastAPI test client transport |
| psutil | process RSS / system RAM for `/api/metrics` (memory budget, SPEC §2) |
| opencv-python, numpy | webcam probe now; the video path from Phase 1 |
| pytest, pytest-asyncio, ruff | test + lint toolchain named in CLAUDE.md |
| react, react-dom, react-router-dom | the three-page UI (SPEC §17) |
| vite, @vitejs/plugin-react, typescript, tailwindcss, postcss, autoprefixer | build toolchain named in CLAUDE.md rule #14 |

No component library was added (rule #14). `recharts` is deferred to Phase 8b.

### Known gaps (deliberate, not defects)

1. **No models, no video, no events.** `/api/health` reports every model-backed
   feature as unavailable until the weights exist locally; that is the design
   (rule #1), not a failure.
2. **`create_all()` runs at startup alongside Alembic.** Convenient for first run,
   but Alembic is the source of truth for schema changes. If the two ever disagree,
   trust the migration; revisit before the first schema change in Phase 1.
3. **Settings overrides are not hot-reloaded into running components.** Each request
   reads effective settings fresh, which is fine now. Once the Phase 1 camera loop
   holds settings in memory, a change to `DETECTION_FPS` will need an explicit
   restart-or-notify path.
4. **The webcam probe opens index `WEBCAM_INDEX` briefly.** It releases in a
   `finally`, but on macOS the first call triggers the camera permission prompt.
   Multi-index probing (`/api/webcams`) is Phase 1.
5. **No integration tests yet** — there is nothing to integrate until Phase 1.
   The `slow` marker is registered and unused.
6. **Frontend has no test runner.** Deliberate for a scaffold; the build runs under
   TypeScript strict mode, which is the current guard. Revisit if the UI grows
   logic worth unit-testing.
7. **Sandbox note:** this phase was written and tested in a Linux container, so the
   webcam probe there reported "opencv not installed" rather than exercising a real
   camera. The laptop acceptance checks are what validate the hardware paths.

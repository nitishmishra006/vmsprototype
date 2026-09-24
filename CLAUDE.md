# CLAUDE.md — Vision VMS prototype

Read this file and `docs/SPEC.md` before every task. The spec is the source of truth. If a request conflicts with the spec, say so before coding.

## What this project is
A natural-language Vision Management System prototype. Hierarchical pipeline: fast detector + tracker on every sampled frame → world model → deterministic event engine → candidate event → evidence → (small VLM) → quality engine → alert → human feedback. The VLM never looks at every frame.

## Target machine
8 GB RAM laptop, CPU-only by default, built-in webcam as the default test camera. Backend peak RAM target ≤ 3.5 GB. Smallest open-source models (see SPEC §4). Run natively (Python venv + npm); Docker is optional.

## Phase discipline
- Work on exactly one phase per session (BUILD_PROMPTS.md). Do not start later phases "while you're there".
- End every phase with: tests passing, the acceptance checks run and their output shown, a short CHANGELOG entry in `docs/PROGRESS.md`, and a list of known gaps.
- If something cannot be done, stop and explain. Do not paper over it.

## Hard rules
1. **No fake implementations.** Never return hard-coded detections, verdicts or scores. If a model is unavailable, the provider raises `ModelUnavailableError` with install instructions, `/api/health` reports it, and the UI shows it as unavailable.
2. **Models load once**, through `app/core/model_registry.py` (lazy, cached, idle-unload, logs device, load time, model version). Never load a model inside a per-frame function. Never import torch/transformers at module level in API/router modules.
3. **Provider interfaces are mandatory** (`app/providers/base.py`). Application code depends on interfaces, never on a concrete model library.
4. **The camera loop never blocks** on the VLM, the parser LLM, Grounding DINO, disk writes of evidence, or the DB. Use the queue / thread pool.
5. **No silent fallbacks.** GPU→CPU, LLM parser→regex, VLM timeout: each is logged at WARNING and recorded on the affected object.
6. **Validate every model output** with Pydantic. Unparseable VLM/LLM output becomes an explicit `unclear` / parse-error result, never an exception that kills a worker.
7. **Everything tunable lives in config** (`app/core/config.py`, pydantic-settings, `.env`). No magic numbers in services.
8. **Structured JSON logs** with the fields in SPEC §22.
9. **Traceability:** every event row links camera, plan, frames, model ids/versions, every score component and the decision reason.
10. **Safety semantics:** high/critical severity events can be downgraded to REVIEW by the VLM but never silently deleted. Never claim certainty in UI text.
11. **Feedback is append-only.** No automatic fine-tuning. Improvements (SPEC §14b) are **proposed → replayed on labelled events → approved by a human → versioned → reversible**. Never apply a change without the user pressing Improve.
12. **Only `StorageProvider` touches the data filesystem.**
13. Keep dependencies minimal. Adding a dependency requires a one-line reason in `docs/PROGRESS.md`.
14. Keep the frontend simple: React + Vite + Tailwind, no component libraries unless asked. **Exactly three pages: Prompt, Events, Settings** (SPEC §17). New features go into a Settings section, not a new page.
15. The laptop webcam is a first-class source. Every phase's acceptance must be testable with the webcam alone.

## Code layout
```
backend/app/{main.py, api/, core/, db/, schemas/, services/, providers/{detector,grounding,embedding,tracker,vlm,parser,storage,video}/, workers/}
backend/tests/{unit,integration}/
frontend/src/{pages,components,services,hooks,models}/
scripts/  data/  docker/  docs/
```

## Commands
```
# backend (from backend/)
source .venv/bin/activate           # Windows: .venv\Scripts\activate
uvicorn app.main:app --reload --port 8000
pytest -q                           # fast tests
pytest -q -m slow                   # tests that load real models
ruff check . && ruff format --check .

# frontend (from frontend/)
npm run dev -- --port 3000
npm run build
```

## Definition of done for any change
Tests added/updated and passing; `ruff` clean; `/api/health` accurate; no new blocking call in the camera loop; RAM impact noted if a model was added.

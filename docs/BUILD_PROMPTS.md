# Build Prompts — Vision VMS Prototype (8 GB laptop)

How to use this file:
1. Do the one-time laptop setup (Part A).
2. Create the repo, put `CLAUDE.md` at the root and `SPEC.md` at `docs/SPEC.md`.
3. Paste **one prompt per session** into your coding agent (Claude Code recommended), in order.
4. After each prompt: run the acceptance checks yourself, commit (`git commit -m "phase N"`), then move on. If something fails, use the Fix prompt (Part C).

---

## Part A — One-time laptop setup

Prerequisites: Python 3.11, Node.js 20+, git, ffmpeg. Close heavy apps (browser tabs) while testing — 8 GB is tight.

```bash
mkdir vision-vms && cd vision-vms && git init
mkdir -p docs backend frontend scripts data/demo
# copy CLAUDE.md to ./ and SPEC.md to ./docs/SPEC.md

# Python env (CPU-only PyTorch FIRST, so ultralytics does not pull the large CUDA build)
cd backend
python3.11 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
# (If you do have an NVIDIA GPU, install the CUDA build from pytorch.org instead.)
cd ..
```

Ollama (for the natural-language parser, Phase 4):
```bash
# Install from https://ollama.com (Windows/macOS installer, or Linux script), then:
ollama pull qwen2.5:1.5b
# optional, only if RAM allows, for a stronger VLM later:
# ollama pull moondream
```

Model downloads (can also happen automatically on first use):
```bash
source backend/.venv/bin/activate
pip install ultralytics "huggingface_hub[cli]"
yolo predict model=yolo11n.pt source=https://ultralytics.com/images/bus.jpg   # downloads yolo11n.pt
huggingface-cli download IDEA-Research/grounding-dino-tiny
huggingface-cli download facebook/dinov2-small
huggingface-cli download HuggingFaceTB/SmolVLM-500M-Instruct
# smaller fallback VLM if 500M is too slow:
# huggingface-cli download HuggingFaceTB/SmolVLM-256M-Instruct
```

Optional speed-up on Intel CPUs (use after Phase 1 works):
```bash
yolo export model=yolo11n.pt format=openvino imgsz=416
```

Check your webcam works with OpenCV (the app's default test camera):
```bash
source backend/.venv/bin/activate
pip install opencv-python
python -c "import cv2; c=cv2.VideoCapture(0); ok,f=c.read(); print('webcam ok' if ok else 'webcam NOT readable', f.shape if ok else ''); c.release()"
```
- macOS: the first run asks for Camera permission for your Terminal/IDE — allow it (System Settings → Privacy & Security → Camera), then restart the terminal.
- Windows: close Teams/Zoom/Meet first; only one app can hold the webcam.
- Linux: your user must be in the `video` group; the device is `/dev/video0`.

Demo video (optional, for scenes you can't create at your desk): put 1–3 short (30–90 s, 720p) royalty-free clips of people walking near vehicles / a warehouse into `data/demo/` (e.g. `factory.mp4`). Clips from your own sites are even better.

Simulate an RTSP camera from an MP4 (to test the RTSP path without hardware):
```bash
# download the mediamtx binary from its GitHub releases page and run it:
./mediamtx
# in another terminal, loop the MP4 as an RTSP stream:
ffmpeg -re -stream_loop -1 -i data/demo/factory.mp4 -c copy -f rtsp rtsp://localhost:8554/cam1
# add camera in the app with URL rtsp://localhost:8554/cam1
```

---

## Part B — Phase prompts

### Prompt 0 — Scaffold

```
Read CLAUDE.md and docs/SPEC.md (all of it). Implement Phase 0: the project scaffold only. No models, no video yet.

Backend (backend/):
- FastAPI app in app/main.py with lifespan startup/shutdown, CORS for http://localhost:3000.
- app/core/config.py: pydantic-settings Settings with EVERY key from SPEC §21, typed, with defaults; write backend/.env.example from it. Runtime overrides: a settings_overrides table merged over .env values; GET /api/settings (effective values + source env|override) and PATCH /api/settings (validated against the Settings types; unknown keys rejected).
- app/core/logging.py: structured JSON logging (one JSON object per line) with the fields in SPEC §22 as optional extras.
- app/core/device.py: resolve DEVICE=auto|cpu|cuda; log the decision and reason; WARNING if cuda requested but unavailable.
- app/core/model_registry.py: ModelRegistry with register(name, factory), get(name) (lazy load, cached), unload(name), idle-unload background task using MODEL_IDLE_UNLOAD_SECONDS, LOW_MEMORY_MODE mutual exclusion group support, status() for health. Records load time, device, model_id, model_version.
- app/providers/base.py: all ABCs and data classes from SPEC §5 (Detection, TrackedObject, EventPackage, VLMVerdict, ParseResult with blockers/warnings, etc.) plus ModelUnavailableError.
- app/providers/storage/local.py: LocalStorageProvider (SPEC §19).
- app/db/: SQLAlchemy 2.0 models for ALL tables in SPEC §18 (JSON columns where needed), session management, Alembic initialised with the first migration. No SQLite-specific features.
- app/schemas/: Pydantic schemas for API I/O and the Monitoring DSL from SPEC §8 (fully typed, with validators for condition params per type).
- app/api/: routers mounted under /api; implement GET /api/health, GET /api/metrics (process RSS, system RAM, CPU %, GPU if torch.cuda available — import torch lazily) and GET /api/setup-status (checklist items: DB, storage, detector weights file present, Ollama reachable + PARSER_MODEL pulled, each HF model present in the local HF cache, at least one webcam openable (quick probe of index WEBCAM_INDEX, released immediately), free disk space; each item has ok, detail, fix_command). Other endpoints from SPEC §20 as routers returning 501 with a clear message.
- requirements.txt (excluding torch, which is installed separately — note this at the top), pyproject with ruff + pytest config, pytest marker "slow".
- tests/unit: test_config (incl. overrides), test_dsl_schema (valid and invalid plans), test_storage_local, test_health, test_setup_status (with mocked probes).

Frontend (frontend/):
- Vite + React + TypeScript + Tailwind. React Router with EXACTLY three pages and a top nav: Prompt (/), Events (/events), Settings (/settings). src/services/api.ts (typed fetch wrapper, base URL from VITE_API_URL default http://localhost:8000).
- Settings page: the Setup checklist at the top (green/red items, fix command with a copy button), then collapsible sections with anchors #cameras #zones #calibration #anchors #concepts #models #thresholds #learning. #thresholds is functional now (edit via PATCH /api/settings, "reset to .env"). The others show "Available after Phase N".
- Prompt and Events pages: page titles and an empty state only.

Scripts: scripts/dev.sh (and scripts/dev.ps1 for Windows) that start backend and frontend.
docs/PROGRESS.md with a Phase 0 entry.

Acceptance (run these and show output):
1. pytest -q passes.
2. uvicorn app.main:app --port 8000 starts; /api/health and /api/setup-status return JSON; /docs loads.
3. npm run dev -- --port 3000 serves the app with three nav items; Settings shows the checklist with correct webcam/Ollama/model status for THIS laptop.
4. Changing a threshold in Settings persists across a backend restart.
5. Process RSS at idle is reported by /api/metrics.
Stop after Phase 0 and summarise what was built and any gaps.
```

### Prompt 1 — Webcam / video source, detection, tracking, live view

```
Read CLAUDE.md and docs/SPEC.md §3–§6 and §17. Implement Phase 1 only.

- providers/video/: three VideoSource implementations. Each runs a decoder thread that keeps ONLY the latest frame + timestamp (drop stale frames) and exposes status online/offline + reason.
  - WebcamVideoSource: cv2.VideoCapture(index, backend) with the backend chosen per OS (Windows: CAP_DSHOW, fallback CAP_MSMF; macOS: CAP_AVFOUNDATION; Linux: CAP_V4L2), requests WEBCAM_WIDTH×WEBCAM_HEIGHT, releases the device on stop. If it cannot open or read (device busy in another app, macOS permission denied), status=offline with a human-readable reason and retry with backoff. Log the backend used.
  - FileVideoSource (MP4, loops, paces to native FPS or CAMERA_FPS).
  - RTSPVideoSource (OpenCV FFMPEG backend, TCP transport, reconnect with backoff).
- GET /api/webcams: probes indexes 0..WEBCAM_MAX_PROBE-1 (skipping indexes used by a running pipeline), returns index, resolution, ok, and a small base64 JPEG thumbnail. Every probe releases the device. Must not hang: per-index timeout.
- Camera types: webcam (index) | file (path) | rtsp (url). POST/GET/DELETE /api/cameras.
- providers/detector/yolo.py: YOLODetectorProvider (ultralytics), model from DETECTOR_MODEL (.pt or exported OpenVINO folder), imgsz=DETECT_IMGSZ, conf=DETECTOR_CONF, class filter from DETECTOR_CLASSES ("all" = all 80 COCO classes). Loaded via ModelRegistry. Records model version.
- providers/tracker/bytetrack.py: ByteTrackTrackerProvider using `supervision` ByteTrack. Stable ids formatted "<class>_<id>".
- services/camera_service.py: CameraPipeline per camera = decoder thread + inference loop thread at DETECTION_FPS. Measures source FPS and inference FPS. Pipelines isolated; one failing camera never affects another. Start/stop on create/delete; restore on app start.
- services/world_model.py: WorldModel per camera as in SPEC §6 (ground point = bottom-centre, trajectory capped, speed px/s for now, first/last seen, age_frames); expire objects not seen for TRACK_BUFFER_FRAMES.
- API: GET /api/cameras/{id}/stream (MJPEG, annotated boxes + ids via supervision annotators, ~5 fps), GET /api/cameras/{id}/snapshot, GET /api/world/{camera_id}, WS /ws/world/{camera_id} (~2 pushes/s).
- Logs: per inference batch at DEBUG (camera_id, model, version, inference_ms, n_detections); per-camera stats every 10 s at INFO.
- Frontend:
  - Prompt page: camera dropdown, live MJPEG view, one stats line (source FPS, inference FPS, objects, CPU/RAM), side list of tracked objects (id, class, conf). If NO camera exists: a big "Use my laptop webcam" button (calls /api/webcams, picks the first ok index, creates the camera, starts the view) and a small "Add another source" link to /settings#cameras. The prompt textbox is visible but disabled with "Available after Phase 2".
  - Settings #cameras: add Webcam (dropdown with thumbnails from /api/webcams), Video file (path), RTSP (URL); list with status + offline reason; delete.
- Tests: unit tests for world model (ground point, trajectory cap, expiry, speed) and webcam backend selection per OS (mock platform); integration test (slow) on a 5-second MP4 clip asserting detections and stable track ids.

Acceptance (run and show output):
1. Fresh DB → Prompt page → "Use my laptop webcam" → live view shows me with a person box and a stable id within 5 s.
2. Holding up a phone, cup or bottle shows it detected and labelled.
3. Inference FPS ≥ 3 at 640×480 (report actual number and RSS).
4. Deleting the webcam camera releases the device (OS camera light turns off; another app can open it).
5. With the webcam held by another app, the camera shows offline with a clear reason — no crash, and it recovers after the other app closes.
6. MP4 source works; RTSP via mediamtx works and reconnects after ffmpeg restarts.
7. pytest -q and pytest -q -m slow pass.
Stop after Phase 1.
```

### Prompt 2 — Zones, rules, events, evidence, feedback (Milestone 1)

```
Read CLAUDE.md and docs/SPEC.md §7, §8, §10, §11, §13, §14, §17. Implement Phase 2 only. This is Milestone 1: webcam/video → detector → tracker → rule → event → evidence → Events page → human feedback. No LLM, no VLM, no open-vocab yet.

- Zones: every camera gets an implicit "whole_frame" zone. API POST/GET /api/cameras/{id}/zones, DELETE /api/zones/{id}; polygons in normalised coords. Settings #zones: pick camera, snapshot, click points, close polygon, name + type, save; supports deep-link prefill (/settings#zones?camera=<id>&name=<name>) and shows a "Back to prompt" button when opened from the Prompt page. Zones drawn on the live view.
- services/event_engine.py: evaluates enabled MonitoringPlans each inference tick. Condition types this phase: present, in_zone, outside_zone, enters_zone, exits_zone, count_in_zone_above, absent_from_zone, overlaps, near/far in PIXELS. Per-binding state with duration_s and CONDITION_GRACE_SECONDS; cooldown per (plan, binding) with EVENT_COOLDOWN_SECONDS; MAX_EVENTS_PER_PLAN_PER_MINUTE. Pure evaluation functions, unit-testable without video.
- services/evidence_service.py: per-camera ring buffer at EVIDENCE_FPS (JPEG at EVIDENCE_WIDTH + tracked objects per frame). On candidate: wait EVIDENCE_POST_SECONDS without blocking the camera loop, then save the package (SPEC §11) via StorageProvider only. package.json must include per-frame tracked-object data (ids, classes, boxes, confidences, ground points, timestamps) for the whole window — Phase 8b replays events from this data. Daily retention job (EVIDENCE_RETENTION_DAYS, keep anything with feedback).
- services/quality_engine.py: SPEC §13 as a pure function (VLM off this phase). Store components, weights, thresholds, decision reason.
- workers/event_worker.py: asyncio candidate_event_queue → quality engine → persist event + evidence + quality_scores. Leave a clear hook for the VLM stage (Phase 7).
- Monitoring plans: POST/GET/PATCH/DELETE /api/monitoring-plans (DSL JSON, validated).
- Prompt page: below the live view, an "Advanced" panel with a structured form (entity class, zone, condition, params, duration, severity) + JSON editor → Start monitoring; Active monitors list (name, status, events today, Pause/Resume/Delete). The natural-language box stays disabled until Phase 4. "Report missed event" button → POST /api/cameras/{id}/missed-event (saves the buffer as a false negative).
- Events page: GET /api/events (filters: decision, plan, camera, unlabelled), GET /api/events/{id}, WS /ws/events for live updates. Cards: key image, event type, time, confidence %, decision, explanation generated from measurements (e.g. "No person in zone 'desk' for 11.4 s"), Correct / Wrong / Not sure + reason. Click → evidence view with Before/During/After annotated frames and score breakdown.
- Feedback: POST /api/events/{id}/feedback storing all fields in SPEC §14 (append-only).
- scripts/seed_example_plans.py <camera_id>: webcam plans — "person absent from zone 'desk' for 10 s" (requires the zone), "cell phone present for 3 s", "more than 1 person in whole_frame for 2 s"; video plans — "person in exclusion zone > 3 s", "vehicle enters zone".
- Tests: every condition type, grace handling, cooldown, rate cap, quality engine gates/thresholds, feedback storage, retention job. Integration (slow): MP4 + zone + plan → event with evidence files → feedback row.

Acceptance with the WEBCAM (run and show output):
1. Draw zone "desk" around where you sit. Create "person absent from desk for 10 s". Walk out of view → an event appears on the Events page without refreshing; come back.
2. Create "cell phone present for 3 s", hold up your phone → event.
3. Evidence view shows before/during/after frames with boxes and the score breakdown.
4. Mark one event Wrong with a reason → show the feedback DB row.
5. Staying away does not create repeated events within the cooldown.
6. Inference FPS dropped by no more than ~10% vs Phase 1 (report numbers and RSS).
7. All tests pass.
Stop after Phase 2. This is the milestone — list anything that is not solid.
```

### Prompt 3 — Calibration, proximity, motion

```
Read CLAUDE.md and docs/SPEC.md §6, §7, §8, §10. Implement Phase 3 only.

- Calibration: POST /api/cameras/{id}/calibration with 4 image points (normalised) and 4 world points in metres; compute homography with OpenCV, store it, return reprojection error. Frontend Settings #calibration (deep-linkable, with Back to prompt): click 4 floor points on a snapshot, enter a rectangle width/length in metres (or 4 explicit world coords), show error; show "calibrated / uncalibrated" badge on the camera.
- World model: ground_point_m and speed in m/s when calibrated; px/s otherwise. Speed smoothed over SPEED_WINDOW_SECONDS.
- Event engine: near/far in metres when units="m" (validation error if camera uncalibrated, with a clear message), approaching, moving_away (distance derivative over a window with a minimum change threshold), moving, stopped, speed_above. Relationships computed only for pairs referenced by enabled plans.
- World endpoint/WS include relationships for active plan pairs (NEAR/FAR/INSIDE/OUTSIDE/APPROACHING/MOVING_AWAY/OVERLAPPING; IN_FRONT_OF/BEHIND marked approximate).
- Live view: optional overlay line between bound pairs showing live distance.
- Since COCO has no forklift, the demo proximity plan uses person ↔ car/truck. Add docs/FORKLIFT.md describing how to fine-tune YOLO11n on a forklift dataset in Google Colab (free GPU) and drop the resulting weights into DETECTOR_MODEL; include the Colab steps as a script scripts/train_forklift_colab.py. Do not train on this laptop.
- Tests: homography round-trip, metre distance, approaching/moving_away/stopped with synthetic trajectories, speed smoothing, validation error for metres on uncalibrated camera.

Acceptance: calibrate the webcam against a known rectangle on your floor or desk (e.g. an A4 sheet: 0.297 × 0.210 m) and check a measured distance with a ruler; then on the demo video calibrate roughly, create "person within 3 m of a moving truck for 1 s", show an event with measured min distance in metres in the explanation; all tests pass. Stop after Phase 3.
```

### Prompt 4 — Natural-language prompts with "Needs setup"

```
Read CLAUDE.md and docs/SPEC.md §8, §9, §17. Implement Phase 4 only.

- providers/parser/ollama_parser.py: OllamaPlanParser calling OLLAMA_URL /api/chat with PARSER_MODEL, temperature 0, keep_alive OLLAMA_KEEP_ALIVE, `format` = JSON schema of the DSL. System prompt includes: the DSL, available detector classes, concepts, anchors, zones (incl. whole_frame) and calibration status for the selected camera, the synonym table, and 8–10 few-shot examples (absent from desk, phone present, count people, object near object in px, zone dwell, proximity in m, "climbs onto" → semantic, "anything unusual" → SEMANTIC_MONITORING, unknown class, zone that does not exist yet).
- One repair round with validation errors, then RegexPlanParser fallback (present; in/inside/enters/leaves/absent from zone; more than N X; X within N m|px of Y; moving/stopped; for N seconds; severity words).
- services/query_parser.py: orchestrates LLM → validate → repair → regex, then the requirement check from SPEC §9 producing blockers and warnings, each with fix {settings_section, prefill}. Also produces plain_text (one or two sentences describing the plan). Log WARNING on fallback. Parsing must never create zones or plans by itself.
- API: POST /api/monitoring-plans/parse {text, camera_id} → ParseResult. Creation stays POST /api/monitoring-plans.
- Prompt page: enable the "What should I capture?" box + example chips. Parse → result panel:
  - plain-language preview,
  - "Needs setup" red list, each item with a "Set now" button → navigates to /settings#<section>?<prefill>&return=<encoded prompt text>; after saving there, "Back to prompt" returns and re-parses automatically,
  - amber warnings,
  - "Start monitoring" disabled while blockers exist,
  - Advanced toggle with the editable JSON.
- Tests: regex parser (≥ 15 sentences), orchestrator with mocked Ollama (valid, invalid-then-repaired, unreachable → regex), requirement check for every blocker/warning type, fix-link prefill.

Acceptance with the WEBCAM (show the parse JSON and what the UI did for each):
1. "Alert me if nobody is at my desk for 10 seconds" on a camera without a 'desk' zone → blocker zone_missing → Set now → draw it → Back to prompt → blocker gone → Start → walk away → event.
2. "Tell me when I pick up my phone" → phone present plan + approximated_phrase warning.
3. "Alert if more than one person is in view for 2 seconds" → count on whole_frame; test with a second person or a photo of a person on your phone.
4. "Alert if a bottle stays near my laptop for 5 seconds" → near in px + uncalibrated_pixels warning.
5. "Alert when a worker gets within 2 metres of a forklift" → blockers calibration_required and class_not_in_detector(forklift) with its fix options.
6. "Tell me whenever something unusual happens at my desk" → SEMANTIC_MONITORING + semantic_experimental warning.
7. Stop Ollama → sentence 1 still parses via regex with a parser_fallback_used warning.
Report parse latency. Stop after Phase 4.
```

### Prompt 5 — Open-vocabulary detection and anchors

```
Read CLAUDE.md and docs/SPEC.md §4, §7, §15 (proposal part). Implement Phase 5 only.

- providers/grounding/grounding_dino.py: GroundingDINOProvider using HF transformers AutoProcessor + AutoModelForZeroShotObjectDetection with GROUNDING_MODEL (grounding-dino-tiny). Prompts are lowercased and joined as "a. b. c." ; use the processor's grounded post-processing with GROUNDING_BOX_THRESHOLD / GROUNDING_TEXT_THRESHOLD; map phrases back to prompt labels. Loaded lazily via ModelRegistry in the LOW_MEMORY_MODE heavy group; runs in a thread pool, never in the camera loop. Cache results per (camera, prompt set, frame hash) briefly.
- services/open_vocab_service.py: (a) on-demand detect on a snapshot, (b) periodic refresh every GROUNDING_INTERVAL_SECONDS for plans that reference open_vocab entities: results are re-associated to existing tracks by IoU, otherwise inserted as refreshed objects with source="open_vocab" and a TTL; the event engine can use them.
- Anchors: POST /api/cameras/{id}/anchors/propose {prompt} → proposals with boxes/scores on the snapshot; POST /api/anchors to save a confirmed (optionally user-adjusted) box with name and optional buffer; GET /api/anchors. Anchors appear in the world model as static objects and can be used in plans (kind: anchor) and by near/overlaps/in_zone(buffer).
- DSL/parser: open_vocab and anchor entity kinds wired end to end; parser context includes anchors.
- Frontend Settings #anchors (deep-linkable from the anchor_missing blocker, with Back to prompt): prompt box, show proposals over the snapshot, select/adjust, save. Live view on the Prompt page draws anchors.
- /api/health shows grounding model loaded/unloaded, device, last latency.
- Tests: prompt formatting, phrase→label mapping, IoU re-association, anchor persistence, mocked provider path; slow test running the real model on one image.

Acceptance: on the demo video, propose an anchor for a visible static object by text, save it, create "alert if a person is within 150 px of <anchor> for 2 s", get an event. Report Grounding DINO latency and peak RSS, and confirm inference FPS is unaffected while it runs. Stop after Phase 5.
```

### Prompt 6 — Visual concepts (DINOv2)

```
Read CLAUDE.md and docs/SPEC.md §15. Implement Phase 6 only.

- providers/embedding/dinov2.py: DINOv2EmbeddingProvider (EMBEDDING_MODEL=facebook/dinov2-small) via transformers; CLS embedding, L2-normalised; embed_batch; cosine similarity. Lazy via ModelRegistry (small, may stay resident).
- services/concept_service.py: create concept (name, description, 3–5 images; reject <3 with a clear message), store images via StorageProvider and embeddings in DB, prototype = normalise(mean). Leave-one-out consistency check with a warning if any reference is an outlier. Rename, delete, add images (recompute prototype). Test against camera: Grounding DINO proposals for the description on the current snapshot → crop → embed → similarity → accepted if ≥ EMBEDDING_THRESHOLD; return all proposals with both scores.
- Concepts as plan entities (kind: concept): the open-vocab refresh path for concept entities filters proposals by embedding similarity; matched objects carry concept_similarity, used by the quality engine's concept component.
- API: POST/GET/PATCH/DELETE /api/concepts, POST /api/concepts/{id}/images, POST /api/concepts/{id}/test.
- Frontend Settings #concepts (deep-linkable from concept_missing / class_not_in_detector blockers): create form with 3–5 image upload + description, list with thumbnails, consistency warning, Test on camera (show proposals with scores, accepted in green, rejected in grey), rename/delete. Webcam test: photograph one of your own objects (a specific mug) 3–5 times with your phone and create a concept from it.
- scripts/create_sample_concept.py: builds a sample concept (e.g. "delivery truck") by running the detector on data/demo/factory.mp4, cropping 5 diverse truck/car crops, and creating the concept via the service.
- Tests: prototype math, normalisation, leave-one-out, threshold logic, concept CRUD, mocked end-to-end matching; slow test with real DINOv2 on sample crops.

Acceptance: sample concept created; "Test on camera" shows matches with scores; a plan referencing the concept produces an event whose score breakdown includes the concept component. Report RSS. Stop after Phase 6.
```

### Prompt 7 — VLM verification and full quality engine

```
Read CLAUDE.md and docs/SPEC.md §12 and §13. Implement Phase 7 only.

- providers/vlm/smolvlm.py: SmolVLMProvider with VLM_MODEL (HuggingFaceTB/SmolVLM-500M-Instruct) via transformers AutoProcessor + AutoModelForVision2Seq (or the class the model card specifies), CPU float32 unless CUDA available (then float16). Lazy load in the LOW_MEMORY_MODE heavy group, idle unload. Input: the evidence 2×2 grid image + prompt from SPEC §12. max_new_tokens small (~80). Greedy decoding.
- providers/vlm/ollama_vlm.py: OllamaVLMProvider (optional backend, e.g. moondream) with the same interface.
- Robust parsing into VLMVerdict (extract first JSON object; accept loose "yes/no" text; else unclear). Keep raw_text, latency_ms, model_version.
- workers/vlm_worker.py: consumes candidates after evidence is saved, MAX_VLM_CONCURRENT_REQUESTS, VLM_TIMEOUT_SECONDS (timeout → proceed without VLM and flag), respects VLM_MODE. Camera loop and alert creation for VLM_MODE=off must be unaffected.
- Quality engine: enable VLM adjustment exactly as SPEC §13 (boost, penalty, high/critical cannot drop below REVIEW). Store vlm_results rows.
- verify_and_explain mode: second short call asking for a one-sentence description, shown in the alert.
- Frontend Events page: cards show VLM answer + reason (or "VLM skipped/timed out"), evidence modal shows the grid image sent to the VLM and the full score breakdown before/after VLM. Settings #models shows VLM model status, device, average latency, queue length and a VLM mode toggle.
- /api/metrics: VLM queue length, avg latency, timeouts.
- Tests: parser for many VLM output styles (clean JSON, JSON in prose, bare yes/no, garbage), quality engine VLM paths incl. severity rule, worker timeout with a slow fake provider (a test double defined in tests only), camera loop unaffected while VLM busy. Slow test with the real model on a saved evidence grid.

Acceptance: with VLM_MODE=verify, trigger events on the demo video; show three events with VLM answers and how the decision changed. Report VLM latency and peak RSS, and show inference FPS stayed stable during a VLM call. Then set VLM_BACKEND to the 256M model and report the difference. Stop after Phase 7.
```

### Prompt 8 — Learning queue, unknown objects, semantic monitoring

```
Read CLAUDE.md and docs/SPEC.md §8 (SEMANTIC_MONITORING), §14, §16. Implement Phase 8 only.

- services/feedback_service.py + learning queue builder (runs every few minutes and on new feedback): LOW_CONFIDENCE_EVENT, REPEATED_FALSE_POSITIVE (≥ N wrong for same plan+zone in 24 h, N configurable), REPEATED_FALSE_NEGATIVE, VLM_DISAGREED_WITH_HUMAN, NEW_VISUAL_CONCEPT, UNKNOWN_OBJECT_CANDIDATE. Idempotent. GET /api/learning-queue.
- scripts/export_dataset.py: exports labelled events (images + YOLO-format boxes + labels.csv with human labels) to data/exports/<timestamp>/.
- Unknown object discovery (off by default, UNKNOWN_DISCOVERY_ENABLED): SPEC §16 exactly; dedupe by embedding; GET /api/unknown-candidates; dismiss; "Create concept" pre-fills the crop as a reference.
- SEMANTIC_MONITORING plans: trigger on scene-change score (frame-difference/SSIM on downscaled frames inside the plan's zone or anchor region, above SCENE_CHANGE_THRESHOLD, with cooldown) or new unknown candidate in the region; VLM describes; decisions capped at REVIEW. UI labels these "Experimental – semantic".
- Frontend Settings #learning: Learning Queue (grouped by type, links to events) and Unknown Candidates (Dismiss / Create concept → opens #concepts prefilled). Events page: semantic events carry an "Experimental" badge.
- Tests: queue rules with synthetic feedback, dedupe, scene-change scoring, SEMANTIC plans never produce ALERT.

Acceptance: after marking several events Wrong for the same plan, a REPEATED_FALSE_POSITIVE item appears; export produces a valid folder; with discovery enabled, at least one unknown candidate appears on the demo video. Stop after Phase 8.
```

### Prompt 8b — Self-improvement loop (Improve button)

```
Read CLAUDE.md and docs/SPEC.md §11, §13, §14, §14b, §15, §17. Implement Phase 8b only.

- Versioning: plan_versions and concept_versions tables. Editing or improving a plan/concept creates a new version; events store plan_version_id / concept_version_id. GET /api/monitoring-plans/{id}/versions.
- Make sure evidence packages and missed-event records contain per-frame tracked-object data (ids, classes, boxes, confidences, ground points, timestamps) for the whole buffer window. If Phase 2 stored less, extend it and note that events created before this phase can't be replayed (show that in the UI instead of guessing).
- services/replay_service.py: pure function replay(plan_version, events_with_labels) → re-runs the event engine and quality engine over the stored per-frame data (NO detector re-run), returns per-event outcome and the summary: false alarms removed, correct alerts kept/lost, missed events now caught, not-sure affected. Deterministic; unit-tested on synthetic tracks.
- services/improvement_service.py: suggestion generator for every type in SPEC §14b (raise_min_confidence, increase_duration, decrease_duration/lower_threshold, exclusion_region, concept_add_positive/negative, class_confusion, retrain_ready). Runs after each feedback and every IMPROVE_SCAN_INTERVAL_SECONDS; needs ≥ IMPROVE_MIN_FEEDBACK relevant labels; each suggestion stores the feedback ids that caused it, the proposed change as a diff, and its replay summary. Exclusion regions: cluster the triggering boxes of Wrong events (simple grid/DBSCAN on box centres), propose the padded hull. Proposed values chosen by searching a small grid and picking the one with the best replay result that loses zero Correct alerts if possible.
- Apply / dismiss / rollback per SPEC §14b, including: red warning + confirm if any Correct alert is lost; typed monitor-name confirm for loosening changes on high/critical plans. Applied improvements are logged (who, when, before/after version, replay numbers).
- Concepts: negatives table; matching rule with CONCEPT_NEGATIVE_MARGIN; positives recompute the prototype (new concept version).
- Parser examples: when a user edits compiled JSON before Start, store (text, final plan) in parser_examples; OllamaPlanParser adds the 3 most similar examples to its few-shot list. Listed/deletable in Settings #learning.
- "Export training set" for retrain_ready reuses scripts/export_dataset.py; shows docs/FORKLIFT.md-style Colab steps. No training here.
- API: endpoints in SPEC §20 under /api/improvements.
- Frontend Events page:
  - After marking Wrong: "Improve this monitor" (opens the matching suggestion) or "Need N more labels to suggest a fix".
  - Second tab "Improvements" with a badge count: suggestion cards (plain-language change, e.g. "Only alert when phone confidence ≥ 0.55 (now 0.35)", replay line "Fixes 5 false alarms · keeps 7/7 correct · 0 new misses", example thumbnails of affected events, Improve / Dismiss); exclusion-region suggestions show the polygon over a snapshot; accuracy trend chart per monitor (daily precision and false alarms/hour, with markers at applied improvements, label counts shown); Improvement history with Rollback.
  - Add `recharts` for the chart (note it in PROGRESS.md).
- Tests: each suggestion rule, replay on synthetic data (including a case where a change would lose a Correct alert), grid search picks the safe value, versioning + rollback, high-severity loosening guard, concept negatives matching, parser example retrieval.

Acceptance with the WEBCAM (show UI screenshots or descriptions and the DB rows):
1. False-alarm test: create "cell phone present for 2 s" with a low min confidence. Show the camera a remote control, calculator or dark wallet until it fires as "cell phone" at least 3 times; mark each Wrong ("not a phone"). Also let 3 real phone events fire and mark them Correct. → A raise_min_confidence suggestion appears with replay numbers → Improve → new plan version → repeat the remote test: fewer or no false alarms, real phone still alerts.
2. Exclusion-region test: create "more than 1 person in view for 2 s". Keep a printed photo of a person (or a phone showing a face) at a fixed spot in view so it fires; mark 3 events Wrong ("photo, not a person"). → exclusion_region suggestion drawn around the photo → Improve → it stops firing for the photo but fires when a real second person enters elsewhere.
3. Rollback the improvement from test 1 → behaviour returns to the old version; history shows both.
4. Accuracy trend chart for the phone monitor shows precision rising after the improvement marker.
5. Concept test (if Phase 6 done): mark a wrong concept match Wrong → concept_add_negative → Improve → that object no longer matches in "Test on camera".
6. All tests pass.
Stop after Phase 8b.
```

### Prompt 9 — Packaging, docs, benchmarks

```
Read CLAUDE.md and docs/SPEC.md. Implement Phase 9 only: packaging and documentation. No new features.

- docker/: backend Dockerfile (python:3.11-slim, CPU torch wheels, non-root user), frontend Dockerfile (build + nginx on port 3000 proxying /api and /ws to backend). docker-compose.yml with services backend (8000), frontend (3000), optional ollama service under a "parser" profile, and a "gpu" profile using the NVIDIA runtime. Volumes for data/ and HF cache. `docker compose up` must work on CPU. Webcam inside Docker works only on Linux via device passthrough (/dev/video0); document that on macOS/Windows the webcam needs the native run.
- README.md: architecture explanation with the pipeline diagram, native setup (primary for 8 GB laptops), Docker setup, exact commands, model download commands, RAM/CPU expectations with the numbers measured in earlier phases (read docs/PROGRESS.md), GPU requirements for the next stage, Jetson deployment notes (L4T base images, TensorRT export of the detector, FP16, hardware decode via GStreamer/nvv4l2decoder, VLM on a separate server), licensing notes (YOLO AGPL), known limitations, next steps to production.
- scripts/benchmark.py: runs the pipeline on data/demo for 60 s and reports source FPS, inference FPS, p50/p95 detector latency, RSS peak, and (if enabled) grounding/VLM latency; writes docs/BENCHMARK.md.
- Integration tests completed per SPEC §23; `pytest -q` fast suite < 60 s.
- Example monitoring plans in docs/EXAMPLE_PLANS.md (natural-language text + compiled JSON).
- Final pass: remove dead code, ensure every 501 stub is either implemented or documented as out of scope, ruff clean.

Acceptance: fresh clone → follow README native steps → working app; `docker compose up` → frontend :3000, backend :8000, docs :8000/docs; benchmark report generated. Stop and summarise the whole project status.
```

---

## Part C — Utility prompts

### Fix prompt (use when an acceptance check fails)
```
Read CLAUDE.md. Phase <N> acceptance check <K> failed. Here is exactly what I did and the full output/logs:
<paste>
Find the root cause before changing code. Explain it in 2–3 sentences, then fix it with the smallest change, add a test that would have caught it, and re-run the failing check and the full test suite. Do not touch unrelated files or start later phases.
```

### Review prompt (run at the end of each phase in a fresh session)
```
Read CLAUDE.md and docs/SPEC.md. Review the code for Phase <N> against the spec and the hard rules. Look specifically for: fake/hard-coded model outputs, models loaded outside ModelRegistry, blocking calls in the camera loop, silent fallbacks, magic numbers not in config, missing Pydantic validation of model output, missing traceability fields on events, and untested condition types. Report findings as a list with file:line and severity. Do not change code in this session.
```

### Memory check prompt (if the laptop starts swapping)
```
Read CLAUDE.md. The backend is using too much RAM on my 8 GB laptop (paste /api/metrics and which features were active). Measure RSS per model load, confirm LOW_MEMORY_MODE mutual exclusion and idle unload actually free memory (gc + torch cache), and propose/implement the smallest changes to keep peak backend RSS ≤ 3.5 GB. Show before/after numbers.
```

---

## Part D — Daily run commands (after Phase 0)

```bash
# terminal 1
ollama serve                         # if not already running as a service
# terminal 2
cd backend && source .venv/bin/activate && uvicorn app.main:app --port 8000
# terminal 3
cd frontend && npm run dev -- --port 3000
# open http://localhost:3000   (API docs: http://localhost:8000/docs)
```

## Part E — When to move to the heavy-GPU version

Move only when Milestone 1 (Phase 2) has run on real site footage for a few days and you have feedback data. Then swap, via config and new providers only: a larger permissively licensed detector (or licensed YOLO) with a forklift/crane-specific fine-tune, real-time open-vocab, DINOv2-base, a 3–8B VLM with multi-image input, TensorRT on Jetson. If swapping requires changes outside `providers/` and config, treat that as a bug in the architecture and fix it first.

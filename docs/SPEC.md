# Natural-Language Vision VMS — Prototype Spec v0.3 (Laptop Edition)

Owner: Variphi · Status: prototype · Target: 8 GB RAM laptop, CPU-only (NVIDIA GPU optional)

This is the corrected version of the original v0.1 spec. The architecture principle is unchanged. What changed is model choice, memory budget, build order, and several technical gaps (listed in §0).

---

## 0. Corrections from v0.1

| # | v0.1 said | Now | Why |
|---|-----------|-----------|-----|
| 1 | YOLO detects forklift "if supported" | COCO has **no forklift class**. Prototype uses `person`, `car`, `truck`, `bus`, `motorcycle`, `bicycle`. Forklift comes from a fine-tuned nano model (optional Phase 3b) or from open-vocab anchors. | The flagship example otherwise silently fails. |
| 2 | Distance "image-space or calibrated" | Distance in **metres only after 4-point floor calibration** (homography). Uncalibrated cameras use pixels and the UI says so. Distance is measured between **bottom-centre ground points** of boxes. | Pixel distance changes with depth. |
| 3 | Rule-based NL parser | **Small local LLM with JSON-schema output → Pydantic validation → one repair retry → regex fallback → user confirms the compiled plan in the UI.** | Hand-written NL parsing is brittle; confirmation builds trust. |
| 4 | Grounding DINO periodically, tracked like normal objects | Open-vocab results are either **anchors** (static objects: furnace, press, parked trolley — detected once, confirmed by user, stored as a zone) or **refreshed detections** re-associated to tracks by IoU + embedding. | A detector running every 5 s cannot produce continuous tracks. |
| 5 | DINOv2 matching of "future detected crops" | Crops come from explicit **region proposals**: Grounding DINO output for the concept's text description. | Embeddings need something to propose crops. |
| 6 | Verbs like climbing / fighting / falling / carrying as rules | These are **SEMANTIC** conditions: rule engine creates a candidate on proximity/overlap, VLM decides. UI labels them "experimental". | They are action recognition, not geometry. |
| 7 | Strong VLM | Smallest usable VLM (SmolVLM-500M). Evidence sent as **one 2×2 annotated grid image**, question is **yes/no + short reason**. | Tiny VLMs handle one image and simple questions far better than multi-image JSON. |
| 8 | Quality engine: "don't average" | Explicit **gate → score → VLM adjust → decide** formula (§13). For safety plans the VLM can **downgrade to REVIEW, never delete**. | Traceable, and a safety alert is never silently dropped. |
| 9 | Zones table only | **Zone polygon editor** and **calibration tool** in the UI. | Crane exclusion zones need them. |
| 10 | `docker compose up` as the way to run | **Native run (venv + npm) is primary** on 8 GB. Docker Compose (CPU profile) is provided but optional. | Docker Desktop's VM reserves RAM the models need. |
| 11 | Licensing not mentioned | Ultralytics YOLO is **AGPL-3.0**: fine for an internal prototype, must be licensed or swapped (behind `DetectorProvider`) before commercial deployment. Check every model card. | Commercial risk. |
| 12 | MP4 / RTSP only | **Laptop webcam is a first-class source** (plus MP4 and RTSP). First launch offers "Use my laptop webcam". Detector runs **all 80 COCO classes** by default so desk objects (phone, cup, bottle, laptop, chair) are testable. | Test everything on the laptop itself before any site camera. |
| 13 | Six UI pages | **Three pages: Prompt, Events, Settings.** Parsing a prompt returns **blockers** (missing zone, calibration, concept, model…) with "Set now" links into Settings, then returns to the prompt. | Simple to use; the system tells you what's missing instead of failing silently. |
| 14 | No auto fine-tuning (feedback only collected) | **Self-improvement loop (Phase 8b):** feedback → system *proposes* improvements → **replays them on your labelled past events** → you press **Improve** → change is versioned and can be rolled back. Accuracy trend shows the effect. | You can see the system get better, and nothing changes behind your back. |

---

## 1. Prototype goal

One video source (laptop webcam, MP4 or RTSP) on a laptop, end to end:

`video → detector → tracker → world model → rule → candidate event → evidence → (VLM) → quality engine → alert → human feedback → stored`

Plus: natural-language monitors, custom visual concepts from 3–5 images, open-vocab anchors, a learning queue. Every model sits behind a provider interface so the heavy-GPU version swaps models without touching application logic.

---

## 2. Hardware target and memory budget

Target: 8 GB RAM, 4+ core CPU, no GPU required. `DEVICE=auto` uses CUDA if present and **logs** which device was chosen and why.

Approximate backend memory (lazy models load on first use):

| Component | Approx RAM | Residency |
|---|---|---|
| Python + PyTorch CPU runtime | 0.8–1.0 GB | always |
| YOLO11n detector | ~0.1 GB | always |
| ByteTrack (supervision) | negligible | always |
| Evidence ring buffer (JPEG) | < 0.1 GB | always |
| DINOv2-small | ~0.1–0.2 GB | lazy, stays |
| Grounding DINO tiny | ~0.7–1.0 GB | lazy, unload after idle |
| SmolVLM-500M-Instruct | ~1.5–2 GB | lazy, unload after idle |
| Qwen2.5-1.5B (Ollama, separate process) | ~1.2 GB | Ollama unloads after `keep_alive` |

Rules:
- Backend peak target **≤ 3.5 GB**. Expose RSS in `/api/metrics`.
- `MODEL_IDLE_UNLOAD_SECONDS` unloads lazy models. At most one of {Grounding DINO, VLM} resident at a time when `LOW_MEMORY_MODE=true`.
- Never import torch/transformers at module import time in API modules; load via `ModelRegistry`.
- Input resolution for detection: `DETECT_IMGSZ=416` (320 if slow). Detection 3–5 FPS on CPU is acceptable.

Expected CPU latency (rough, varies by laptop): YOLO11n 30–100 ms/frame; Grounding DINO tiny 2–8 s/image; SmolVLM-500M 10–60 s/answer. All heavy calls are async and off the camera loop.

---

## 3. Pipeline

```
[Decoder thread]  webcam / RTSP / MP4 → keeps latest frame only (drops stale)
      │
[Inference loop]  sample at DETECTION_FPS → DetectorProvider → TrackerProvider
      │            (+ refreshed open-vocab detections, concept matches)
      ▼
[WorldModel]      objects, tracks, trajectories, ground points, anchors, zones, relationships
      ▼
[EventEngine]     evaluates enabled MonitoringPlans every tick → CandidateEvent
      ▼
[EvidenceService] ring buffer → before / during / after frames + metadata
      ▼
[candidate_event_queue] ──► [VLM worker(s), MAX_VLM_CONCURRENT_REQUESTS=1, timeout]
      ▼
[QualityEngine]   gate → score → VLM adjust → ALERT | REVIEW | SUPPRESS
      ▼
[Alert] → UI (WebSocket push) → Human feedback → FeedbackStore → LearningQueue
```

The camera loop never awaits the VLM, the parser LLM, or Grounding DINO.

---

## 4. Model stack (smallest open-source)

| Role | Prototype model | Licence (verify on model card) | When it runs |
|---|---|---|---|
| Known-object detection | Ultralytics **YOLO11n** (COCO), optional OpenVINO/ONNX export | AGPL-3.0 | every sampled frame |
| Tracking | **ByteTrack** via `supervision` | MIT | every sampled frame |
| Open-vocab detection | **Grounding DINO tiny** (`IDEA-Research/grounding-dino-tiny`, HF transformers) | Apache-2.0 | on demand: concept test, anchor setup, plan needing unknown object, every `GROUNDING_INTERVAL_SECONDS` if a plan requires it |
| Image embedding | **DINOv2-small** (`facebook/dinov2-small`) | Apache-2.0 | concept creation, match checks on proposals |
| VLM | **SmolVLM-500M-Instruct** (`HuggingFaceTB/SmolVLM-500M-Instruct`); alt `SmolVLM-256M-Instruct` | Apache-2.0 | candidate events only |
| NL → plan parser | **Qwen2.5-1.5B-Instruct** via Ollama (`qwen2.5:1.5b`) with JSON-schema `format` | Apache-2.0 | when a user creates a monitor |

Optional providers (same interfaces): `OllamaVLMProvider` (e.g. `moondream`, `qwen2.5vl:3b` if RAM allows), `OpenVINODetectorProvider`.

GPU upgrade path (later, no app changes): larger detector (permissive licence), Grounding DINO base / YOLO-World-class real-time open-vocab, DINOv2-base, a 3–8B VLM with multi-image/video input, TensorRT on Jetson.

---

## 5. Provider interfaces (mandatory)

```python
class DetectorProvider(ABC):
    def detect(self, frame: np.ndarray) -> list[Detection]: ...
    @property
    def class_names(self) -> list[str]: ...

class OpenVocabularyProvider(ABC):
    def detect(self, frame: np.ndarray, prompts: list[str],
               box_threshold: float, text_threshold: float) -> list[Detection]: ...

class EmbeddingProvider(ABC):
    def embed(self, image: np.ndarray) -> np.ndarray: ...          # L2-normalised
    def embed_batch(self, images: list[np.ndarray]) -> np.ndarray: ...
    @staticmethod
    def similarity(a: np.ndarray, b: np.ndarray) -> float: ...      # cosine

class TrackerProvider(ABC):
    def update(self, detections: list[Detection], frame_ts: float) -> list[TrackedObject]: ...
    def reset(self) -> None: ...

class VLMProvider(ABC):
    def verify_event(self, pkg: EventPackage) -> VLMVerdict: ...
    def explain_event(self, pkg: EventPackage) -> str: ...

class PlanParserProvider(ABC):
    def parse(self, text: str, context: ParserContext) -> ParseResult: ...

class StorageProvider(ABC):
    def put(self, key: str, data: bytes, content_type: str) -> str: ...
    def get(self, key: str) -> bytes: ...
    def url(self, key: str) -> str: ...
    def delete(self, key: str) -> None: ...

class VideoSource(ABC):   # laptop webcam, MP4 file, RTSP; WebRTC later
    def read_latest(self) -> tuple[np.ndarray, float] | None: ...
```

`Detection`: `bbox_xyxy`, `label`, `confidence`, `source` (`detector|open_vocab|concept`), optional `embedding`.
All models are created by one `ModelRegistry` (load once, lazy, idle-unload, logs device + load time + model version).
Every provider has a `model_id` and `model_version` recorded on every event.

If a model cannot load, the provider raises a clear error and the feature is marked **unavailable** in `/api/health` and the UI. No hard-coded fake results.

---

## 6. Tracking and world model

Per camera, in memory, snapshot to DB on events.

```json
{
  "id": "person_182", "type": "person", "source": "detector",
  "bbox": [100,200,300,600], "confidence": 0.91,
  "ground_point_px": [200,600], "ground_point_m": [3.4, 7.1],
  "first_seen": 1727160000.1, "last_seen": 1727160012.4,
  "age_frames": 57, "speed": 0.8, "speed_units": "m/s",
  "trajectory": [[ts, x, y], ...],          // capped at TRAJECTORY_MAX_POINTS
  "attributes": {}
}
```

- Ground point = bottom-centre of bbox. Metres only if the camera is calibrated.
- Speed from trajectory over `SPEED_WINDOW_SECONDS`, smoothed.
- Relationships computed per tick for entity pairs referenced by enabled plans only (not all pairs): `NEAR, FAR, INSIDE, OUTSIDE, APPROACHING, MOVING_AWAY, OVERLAPPING`. `IN_FRONT_OF / BEHIND` are derived from ground-point y (depth proxy) and marked approximate.
- Anchors (static open-vocab objects) live in the world model like objects with `source: "anchor"`, `static: true`.

---

## 7. Zones, anchors and calibration

- **whole_frame**: every camera has an implicit zone covering the full image, so plans like "a phone is visible" need no drawing.
- **Zone**: named polygon in normalised image coordinates (0–1), drawn on a snapshot in the UI. Types: `exclusion`, `work_area`, `path`, `generic`.
- **Anchor**: Grounding DINO proposal for a text prompt on a snapshot → user confirms/adjusts box → stored as an object with a polygon. Optional buffer (`buffer_m` or `buffer_px`) creates an implicit zone around it.
- **Calibration**: user clicks 4 floor points and enters their real-world coordinates in metres (e.g. a W×L rectangle). `cv2.getPerspectiveTransform` → homography stored per camera. Reprojection error shown to the user.

---

## 8. Monitoring DSL

Pydantic models. The natural-language instruction compiles into this.

```json
{
  "id": "plan_123",
  "name": "Worker near moving forklift",
  "source_text": "Alert me if a worker gets within 2 m of a moving forklift",
  "camera_ids": ["CAM_01"],
  "mode": "DETERMINISTIC",
  "entities": [
    {"alias": "worker",   "kind": "detector_class", "ref": "person"},
    {"alias": "forklift", "kind": "detector_class", "ref": "forklift"}
  ],
  "conditions": [
    {"type": "near",   "subject": "worker", "object": "forklift",
     "params": {"max_distance": 2.0, "units": "m"}},
    {"type": "moving", "subject": "forklift", "params": {"min_speed": 0.3, "units": "m/s"}}
  ],
  "logic": "all",
  "duration_s": 2.0,
  "event_type": "unsafe_proximity",
  "severity": "high",
  "vlm_question": "Is a worker dangerously close to a moving forklift?",
  "enabled": true
}
```

- `entities[].kind`: `detector_class | open_vocab | concept | anchor | zone`.
- Condition types (v1): `present (entity visible, optionally in a zone), in_zone, outside_zone, enters_zone, exits_zone, near, far, overlaps, approaching, moving_away, moving, stopped, speed_above, count_in_zone_above, absent_from_zone, semantic`.
- `semantic` condition: `{ "type": "semantic", "subject": "worker", "object": "trolley", "params": {"action": "climbing", "trigger": "overlaps"} }` — the trigger geometry creates the candidate, VLM decides.
- `logic` is `all` (AND) in v1. OR = create two plans.
- `mode: SEMANTIC_MONITORING` for open-ended instructions ("anything unusual near the furnace"): triggers are scene-change score in a zone/anchor region above `SCENE_CHANGE_THRESHOLD` or new unknown object; VLM describes; decisions default to REVIEW, never ALERT, in the prototype.
- If a plan references a detector class that the loaded detector does not have (e.g. `forklift`), validation fails with a message suggesting: use open-vocab, create a concept, or load a fine-tuned detector.

---

## 9. NL query parser

1. Build context: available detector classes, concepts, anchors, zones, calibration status of target camera.
2. `OllamaPlanParser` → `qwen2.5:1.5b`, `format` = JSON schema of the DSL, temperature 0, few-shot examples.
3. Validate with Pydantic + semantic checks (aliases resolve, classes exist, units possible).
4. **Requirement check** produces `blockers` (plan cannot start) and `warnings` (plan can start). Blocker types: `camera_missing`, `zone_missing(name)`, `calibration_required`, `class_not_in_detector(name)` (fix options: open-vocab / create concept / create anchor / load fine-tuned detector), `concept_missing(name)`, `anchor_missing(name)`, `model_unavailable(name)`. Warning types: `parser_fallback_used`, `approximated_phrase` (e.g. "pick up my phone" → phone present near person), `semantic_experimental`, `uncalibrated_pixels`. Each item carries a `fix` target `{settings_section, prefill}` for the UI.
5. On failure: one repair call with the validation errors. Then `RegexPlanParser` fallback (covers: detect X; X in/enters/leaves zone Z; X within N m/px of Y; for N seconds; moving/stopped).
6. Return `ParseResult{plan, plain_text, blockers, warnings, unsupported_phrases, parser_used}`.
7. UI shows the compiled plan in plain language. **Nothing runs until blockers are resolved and the user clicks Start.**
8. Synonym table in config: worker/person/operator/labour → `person`; vehicle → `car|truck|bus`; etc.

---

## 10. Event engine

- Evaluates each enabled plan per tick against the world model.
- Tracks condition state per binding (e.g. `(plan_id, worker_track, forklift_track)`), start time, and last-true time with `CONDITION_GRACE_SECONDS` to survive 1–2 missed detections.
- When duration is met → `CandidateEvent` with bindings, measured values (min distance, duration, speeds), and rule confidence.
- Cooldown per `(plan_id, binding)` = `EVENT_COOLDOWN_SECONDS`. Also a per-plan rate cap `MAX_EVENTS_PER_PLAN_PER_MINUTE`.
- Candidate goes to evidence collection, then the queue. It is not an alert yet.

---

## 11. Evidence buffer

- Ring buffer per camera at `EVIDENCE_FPS=2`, frames JPEG-encoded at width `EVIDENCE_WIDTH=640`, with the tracked objects for that frame.
- Pre `EVIDENCE_PRE_SECONDS=10`, post `EVIDENCE_POST_SECONDS=5` (candidate waits for post frames before queueing).
- Saved package: all buffered frames (raw), selected keyframes (3 before, 1 during, 2 after) annotated with boxes + IDs + distance line, a 2×2 grid image for the VLM, `package.json` (plan, bindings, measurements, trajectories, timestamps, model versions). Optional short MP4 clip via OpenCV.
- Evidence older than `EVIDENCE_RETENTION_DAYS` is deleted by a daily job unless it has human feedback (webcam footage of yourself should not pile up).

---

## 12. VLM verification

- `SmolVLMProvider` (transformers, CPU, loaded lazily). Input: the 2×2 grid (before-early, before-late, during, after) + text.
- Prompt: plan's `vlm_question` + one-line candidate description + "Answer in JSON: {"answer": "yes"|"no"|"unclear", "reason": "<one sentence>"}".
- Parse: extract first JSON object; Pydantic `VLMVerdict{answer, reason, raw_text, latency_ms, model_version}`. If unparseable → `answer="unclear"`, raw text kept. Never crash the pipeline.
- Tiny models give no calibrated confidence. Map: yes → 0.75, no → 0.25, unclear → 0.5 (config), clearly labelled as a heuristic.
- `VLM_MODE`: `off | verify | verify_and_explain`. `VLM_TIMEOUT_SECONDS`. On timeout → proceed without VLM, flag in the alert.

---

## 13. Quality engine (replaceable scoring function)

```
1. Gates (fail → SUPPRESS, logged with reason):
   rule satisfied; every bound track age ≥ MIN_TRACK_AGE_FRAMES;
   mean detection conf of each bound entity ≥ MIN_DET_CONF
2. Component scores in [0,1]:
   perception = geometric mean of bound entities' mean confidence over the window
   tracking   = fraction of window frames in which each bound entity was observed (min over entities)
   temporal   = min(1, observed_duration / (2 × required_duration))
   concept    = embedding similarity (if a concept entity is bound), else omitted
3. base = weighted mean of available components (weights in config, renormalised)
4. VLM adjustment:
   yes → final = base + (1 − base) × VLM_BOOST
   no  → final = base × VLM_PENALTY; if severity ∈ {high, critical} decision cannot go below REVIEW
   unclear / off / timeout → final = base
5. Decision: final ≥ ALERT_THRESHOLD → ALERT; ≥ REVIEW_THRESHOLD → REVIEW; else SUPPRESS
```

Output stores every component, weights, thresholds and the decision reason. `QualityEngine.score(...)` is a pure function with its own tests so it can later be replaced by a learned model.

---

## 14. Human feedback and learning queue

- Alert and Review items both get **Correct / Wrong / Not Sure** + optional reason text.
- Stored: event_id, camera_id, plan_id, predicted event, final confidence, all components, decision, human label, reason, evidence keys, bindings, model versions, timestamp, user.
- "Report missed event" button on the live view creates a false-negative record with the current buffer.
- Learning queue entries (no auto fine-tuning): `LOW_CONFIDENCE_EVENT` (REVIEW decisions), `REPEATED_FALSE_POSITIVE` (≥ N wrong for same plan+zone in 24 h), `REPEATED_FALSE_NEGATIVE`, `VLM_DISAGREED_WITH_HUMAN`, `NEW_VISUAL_CONCEPT`, `UNKNOWN_OBJECT_CANDIDATE`.
- Export script: dataset folder (images + YOLO-format labels from stored boxes + labels.csv) for future training.

---

## 14b. Self-improvement loop (Phase 8b)

Principle: **propose → replay → human approves → versioned → reversible.** Nothing changes automatically. No model weights are trained on the laptop.

**Where it lives:** Events page, second tab **Improvements**, plus an inline **Improve this monitor** button on an event after it is marked Wrong.

**Suggestion generator** (runs after each feedback and every few minutes; a suggestion needs ≥ `IMPROVE_MIN_FEEDBACK` relevant labels):

| Suggestion | Triggered by | What it changes |
|---|---|---|
| `raise_min_confidence` | Wrong events whose bound detections had low confidence | plan's `min_det_conf` override |
| `increase_duration` | Wrong events that were short (just above `duration_s`) | plan's `duration_s` |
| `decrease_duration` / `lower_threshold` | Missed-event reports or Correct events that barely passed | plan's `duration_s` / alert threshold (always flagged as *loosening*) |
| `exclusion_region` | Wrong events whose triggering boxes cluster in one image area (e.g. a poster or a TV showing a person) | adds an ignore-polygon to the plan |
| `concept_add_positive` / `concept_add_negative` | Correct / Wrong events involving a concept match | adds the crop's embedding to the concept's positives or negatives |
| `class_confusion` | Same detector class repeatedly Wrong with the reason text naming another object | suggests a concept or open-vocab entity instead; no automatic change |
| `retrain_ready` | ≥ `RETRAIN_MIN_LABELS` labelled events for a class | shows "Export training set" (manual Colab fine-tune, SPEC §14); never automatic |

Parser learning: when a user edits the compiled JSON before starting a plan, the (prompt text, final plan) pair is stored as a parser example and used as a few-shot example later. Examples are listed and deletable in Settings #learning.

**Replay (the "what would have happened" check):** every suggestion is evaluated before it is offered as applicable. Replay re-runs the **event engine + quality engine** (not the detector) over the per-frame tracked-object data stored in evidence packages and missed-event buffers, with the current plan and with the proposed change. It reports, over all labelled events for that monitor:
- false alarms removed (Wrong events that would no longer fire),
- correct alerts kept / lost (Correct events that would stop firing),
- missed events now caught (from missed-event reports),
- Not-sure events affected.
Shown as: *"Fixes 5 false alarms · keeps 7/7 correct alerts · 0 new misses"*.

**Applying:**
- **Improve** creates a new `plan_version` (or concept version) with a note of which suggestion and which feedback produced it. The previous version stays and **Rollback** restores it.
- A suggestion that loses any Correct alert shows a red warning and needs an explicit confirm.
- For `high`/`critical` severity plans, any *loosening* change (fewer alerts) requires typing the monitor name to confirm.
- Every event records the plan version and concept version that produced it.

**Seeing the improvement:** Improvements tab shows, per monitor, a daily chart of **precision (% of labelled events marked Correct)** and **false alarms per hour**, with a marker at each applied improvement, plus an **Improvement history** list (what changed, when, replay numbers at the time, Rollback button). Numbers are shown with their label counts (e.g. "83% of 12 labelled") so small samples are obvious.

**Concept matching with negatives:** a proposal matches a concept if `sim(prototype) ≥ EMBEDDING_THRESHOLD` **and** `sim(prototype) − max(sim(negatives)) ≥ CONCEPT_NEGATIVE_MARGIN`. Positives added via Improve update the prototype.

## 15. Visual concepts

- Create: name, description (short text prompt, e.g. "steel ladle"), 3–5 reference images.
- Embed with DINOv2-small, store each L2-normalised embedding and the prototype = normalise(mean).
- Match: Grounding DINO proposals for the description (low box threshold) → crop → embed → cosine vs prototype → accept if ≥ `EMBEDDING_THRESHOLD`. Store both scores.
- Leave-one-out self-check on creation: similarity of each reference to the prototype of the others; warn if the set is inconsistent.
- "Test against camera": run on current snapshot, show proposals with scores (accepted/rejected).
- Rename, delete, add images (prototype recomputed).
- Concepts are referenceable by name in plans (`kind: concept`).

---

## 16. Unknown object discovery (experimental)

Every `UNKNOWN_SCAN_INTERVAL_SECONDS` on a keyframe: Grounding DINO with a generic prompt ("object."), drop boxes overlapping existing tracks/anchors (IoU > 0.3), drop boxes matching any concept, drop tiny boxes → candidates with crop, camera, timestamp. Deduplicate by embedding over time. User can dismiss or "Create concept" (crop pre-filled as first reference). Never creates classes automatically. Off by default.

---

## 17. UI — three pages only (React + Vite + Tailwind)

Top nav: **Prompt · Events · Settings**. First launch opens Prompt; if no camera exists it shows one big button: **"Use my laptop webcam"**.

### Page 1 — Prompt (`/`)
- Camera dropdown + live view (MJPEG with boxes, IDs, zones, anchors) + one stats line (source FPS, inference FPS, objects, CPU/RAM).
- Text box **"What event should I capture?"** + Parse. Example chips (webcam-friendly: "Alert me if nobody is at my desk for 10 seconds", "Tell me when a phone is visible for 3 seconds", "Alert if more than one person is in view").
- Result panel:
  - plain-language preview of the compiled plan;
  - **Needs setup** (red blockers), each with a **Set now** button that opens the exact Settings section with values prefilled (e.g. zone name "desk", this camera). After saving, a **Back to prompt** button returns and re-parses automatically (prompt text kept in the URL);
  - **Warnings** (amber);
  - **Start monitoring** — disabled while blockers exist;
  - "Advanced" toggle: editable JSON plan + structured form.
- Active monitors list: name, camera, status, events today, Pause / Resume / Delete.
- "Report missed event" button (saves current buffer as a false negative).

### Page 2 — Events (`/events`)
- Live list via WebSocket. Filters: decision (Alert / Review / All), monitor, camera, unlabelled first.
- Card: key image, event type, time, confidence %, decision, explanation, VLM answer when present, **✓ Correct / ✗ Wrong / ? Not sure** + optional reason.
- Click → evidence view: Before / During / After annotated frames, clip if saved, score breakdown, model versions, plan version.
- After marking **Wrong**, the card offers **Improve this monitor** if a suggestion exists (or "Need N more labels to suggest a fix").
- Second tab **Improvements** (Phase 8b, SPEC §14b): suggestion cards with replay results and **Improve** / Dismiss buttons, accuracy trend chart per monitor, improvement history with **Rollback**. A badge on the tab shows how many suggestions are waiting.

### Page 3 — Settings (`/settings`)
One page, collapsible sections with anchors so the Prompt page can deep-link (`/settings#zones?camera=CAM_01&name=desk`):
- **Setup checklist** (top, from `/api/setup-status`): webcam/camera present, detector weights, Ollama reachable + parser model pulled, Grounding DINO / DINOv2 / VLM downloaded, disk space. Each unmet item shows the exact command to fix it.
- `#cameras` — add Webcam (dropdown with thumbnails from `/api/webcams`), Video file, RTSP; status with reason; delete.
- `#zones` — polygon editor on a snapshot.
- `#calibration` — 4-point floor calibration.
- `#anchors`, `#concepts` — open-vocab anchors and visual concepts.
- `#models` — status, device, latency, VLM mode toggle.
- `#thresholds` — runtime-editable values grouped by detection / events / evidence / quality, with "reset to .env".
- `#learning` — learning queue and unknown-object candidates.
Sections for phases not yet built show "Available after Phase N" — never fake content.

## 18. Database (SQLite + SQLAlchemy 2 + Alembic)

Tables: `cameras, calibrations, zones, anchors, monitoring_plans, tracked_objects (snapshots on events), events, event_evidence, quality_scores, vlm_results, feedback, visual_concepts, visual_concept_images, unknown_candidates, learning_queue, model_versions, settings_overrides, plan_versions, concept_versions, concept_negatives, improvement_suggestions, applied_improvements, parser_examples`. Events store `plan_version_id` and `concept_version_id`.
JSON columns via SQLAlchemy `JSON` type; no SQLite-only features, so Postgres migration is an Alembic run.

## 19. Storage

`LocalStorageProvider` rooted at `DATA_DIR` with prefixes `cameras/ evidence/ concepts/ feedback/ exports/`. Only this class touches the filesystem; S3/MinIO later.

## 20. API

```
GET  /api/health                 GET  /api/metrics
GET  /api/setup-status           GET  /api/settings    PATCH /api/settings   (runtime overrides)
GET  /api/webcams                (probe local webcams, with thumbnails)
POST /api/cameras                GET  /api/cameras        DELETE /api/cameras/{id}
GET  /api/cameras/{id}/stream    (MJPEG)     GET /api/cameras/{id}/snapshot
POST /api/cameras/{id}/zones     GET  /api/cameras/{id}/zones   DELETE /api/zones/{id}
POST /api/cameras/{id}/calibration
POST /api/cameras/{id}/anchors/propose   POST /api/anchors   GET /api/anchors
POST /api/monitoring-plans/parse         (returns plan, plain_text, blockers, warnings; does not save)
POST /api/monitoring-plans   GET /api/monitoring-plans   PATCH /api/monitoring-plans/{id}   DELETE /api/monitoring-plans/{id}
POST /api/concepts  GET /api/concepts  PATCH /api/concepts/{id}  DELETE /api/concepts/{id}
POST /api/concepts/{id}/images   POST /api/concepts/{id}/test
GET  /api/events  GET /api/events/{id}  POST /api/events/{id}/feedback
POST /api/cameras/{id}/missed-event
GET  /api/learning-queue   GET /api/unknown-candidates
GET  /api/improvements/suggestions        POST /api/improvements/suggestions/{id}/replay
POST /api/improvements/suggestions/{id}/apply    POST /api/improvements/suggestions/{id}/dismiss
GET  /api/improvements/history            POST /api/improvements/history/{id}/rollback
GET  /api/improvements/trend?plan_id=...  (daily precision, false alarms/hour, improvement markers)
GET  /api/monitoring-plans/{id}/versions
GET  /api/world/{camera_id}
WS   /ws/events   WS /ws/world/{camera_id}
```

## 21. Configuration (`.env.example`)

```
DEVICE=auto
LOW_MEMORY_MODE=true
MODEL_IDLE_UNLOAD_SECONDS=120
DATA_DIR=./data
DATABASE_URL=sqlite:///./data/vms.db

WEBCAM_INDEX=0
WEBCAM_WIDTH=640
WEBCAM_HEIGHT=480
WEBCAM_MAX_PROBE=4

CAMERA_FPS=10
DETECTION_FPS=4
DETECT_IMGSZ=416
DETECTOR_MODEL=yolo11n.pt
DETECTOR_CONF=0.35
DETECTOR_CLASSES=all            # all | comma list, e.g. person,car,truck
TRACK_BUFFER_FRAMES=30
TRAJECTORY_MAX_POINTS=200
SPEED_WINDOW_SECONDS=1.0
CONDITION_GRACE_SECONDS=0.5

GROUNDING_MODEL=IDEA-Research/grounding-dino-tiny
GROUNDING_INTERVAL_SECONDS=5
GROUNDING_BOX_THRESHOLD=0.30
GROUNDING_TEXT_THRESHOLD=0.25

EMBEDDING_MODEL=facebook/dinov2-small
EMBEDDING_THRESHOLD=0.70

PARSER_BACKEND=ollama            # ollama | regex
OLLAMA_URL=http://localhost:11434
PARSER_MODEL=qwen2.5:1.5b
OLLAMA_KEEP_ALIVE=60s

VLM_MODE=verify                  # off | verify | verify_and_explain
VLM_BACKEND=smolvlm              # smolvlm | ollama
VLM_MODEL=HuggingFaceTB/SmolVLM-500M-Instruct
MAX_VLM_CONCURRENT_REQUESTS=1
VLM_TIMEOUT_SECONDS=120

EVIDENCE_FPS=2
EVIDENCE_WIDTH=640
EVIDENCE_PRE_SECONDS=10
EVIDENCE_POST_SECONDS=5
EVIDENCE_RETENTION_DAYS=7
EVENT_COOLDOWN_SECONDS=30
MAX_EVENTS_PER_PLAN_PER_MINUTE=4

MIN_TRACK_AGE_FRAMES=3
MIN_DET_CONF=0.35
QUALITY_WEIGHTS=perception:0.4,tracking:0.3,temporal:0.3,concept:0.3
VLM_BOOST=0.5
VLM_PENALTY=0.5
ALERT_THRESHOLD=0.70
REVIEW_THRESHOLD=0.45

UNKNOWN_DISCOVERY_ENABLED=false

IMPROVE_MIN_FEEDBACK=3
IMPROVE_SCAN_INTERVAL_SECONDS=300
CONCEPT_NEGATIVE_MARGIN=0.05
RETRAIN_MIN_LABELS=200
UNKNOWN_SCAN_INTERVAL_SECONDS=30
SCENE_CHANGE_THRESHOLD=0.25
```

## 22. Logging and traceability

Structured JSON logs (one line per record) with: `camera_id, ts, stage, model_id, model_version, device, inference_ms, n_detections, plan_id, event_id, vlm_latency_ms, vlm_answer, quality_components, final_decision`. Device selection and any GPU→CPU fallback logged at WARNING. Every event row links camera, plan, frames, model versions, all scores.

## 23. Tests

Unit: improvement suggestion rules, replay correctness on synthetic evidence, versioning + rollback, concept negatives, DSL validation, requirement check (blockers/warnings), webcam backend selection per OS, regex parser, LLM parser with mocked Ollama, distance px and m (homography), zone inside/enter/exit, temporal persistence with grace, cooldown and rate cap, quality engine (gates, VLM veto → REVIEW for high severity), VLM JSON parsing (valid / garbage / partial), feedback storage, concept prototype + similarity, storage provider.
Integration: MP4 → detector → tracker → plan → event → evidence → alert (real YOLO11n on a short clip); candidate → evidence → VLM (mocked provider + one real opt-in test marked `@pytest.mark.slow`) → quality → alert.

## 24. Out of scope for the prototype

More than 2 simultaneous cameras, WebRTC, auth/RBAC, TensorRT/Jetson builds, automatic fine-tuning, multi-site, HA.

## 25. Build order (see BUILD_PROMPTS.md)

0 Scaffold → 1 Video + detection + tracking + live view → 2 Zones, rules, events, evidence, alerts, feedback (**Milestone 1**) → 3 Calibration, proximity, motion → 4 NL parser + confirmation → 5 Grounding DINO + anchors → 6 DINOv2 concepts → 7 VLM + quality engine → 8 Learning queue, unknown objects, semantic mode → **8b Self-improvement loop** → 9 Packaging, Docker, README, benchmarks.

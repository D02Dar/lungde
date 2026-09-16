# WenT respiratory measurement

A clean two-path respiratory movement prototype built independently from `RespiratoryMovementWeb`.

## Architecture

- **Frontend real-time path:** Vue runs grayscale conversion, per-frame Otsu thresholding, upper-body subject-pixel area measurement, filtering, peak/trough analysis, RR, `VtA`, `VcA`, and `VcA / VtA` locally.
- **Backend offline path:** FastAPI receives the recorded video and the Position-locked `went-roi-v2` chest contract, validates the ROI, segments the subject, locks a continuous upper-thorax row band, and measures phase-constrained Vt/Vc before the independent RR analysis.
- **Review alignment:** the backend aligns normalized Realtime and Offline waveforms and returns a display-only Primary trace with correlation, lag and source weights. Fusion never replaces the formal Offline or Realtime Vc/Vt values.
- **Evidence:** backend stable-hold selection replaces transient client inhale/exhale requests when enough Realtime samples exist; Offline supported landmarks are added from the processed video.
- **Records and export:** the browser keeps the original clip, ROI, protocol phases, Realtime samples, both result objects and evidence timestamps in IndexedDB. Backend analyses are retained in local SQLite/file storage and expose reproducible ZIP exports containing JSON, CSV and SVG.

The two measurement algorithms remain independent. Alignment and export consume their saved outputs but do not feed a fused signal back into Vt, Vc, ratio or RR calculations.

### Production boundary

- Runtime code lives in `frontend/src/` and `backend/app/`; tests live in `frontend/test/` and `backend/tests/`.
- `deliverables/` and `doc/` are review material and are never imported by the application.
- `.codex-*` generated folders and `backend/data/` runtime storage are not production source. Their generated contents are ignored by git.

## Run the frontend

```bash
cd WenT/frontend
npm install
npm test
npm run dev
```

The frontend opens at `http://127.0.0.1:5174`.

## Run the backend

```bash
cd WenT/backend
python -m venv .venv
# Windows PowerShell
.venv/Scripts/Activate.ps1
pip install -e ".[test]"
pytest
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Health check: `GET http://127.0.0.1:8000/api/health`.

The backend uses the FFmpeg binary bundled by `imageio-ffmpeg` when a browser WebM cannot be decoded completely by OpenCV. This handles MediaRecorder WebM files whose duration index is missing or whose VP8/VP9 stream stops early in OpenCV.

## Small remote / school deployment

The preferred first deployment is one HTTPS school server: serve the built Vue files and reverse-proxy `/api` to one FastAPI process. This preserves the default relative frontend API URL and avoids a cross-origin setup.

1. Copy `backend/.env.remote.example` to a private environment file and replace the example hostname with the school's real HTTPS frontend origin.
2. Mount `WENT_DATA_DIR` on persistent storage. Do not put it inside a disposable container or the Git checkout.
3. Configure the reverse proxy upload-body limit to at least `WENT_MAX_VIDEO_MB` and allow a longer upstream timeout for video analysis.
4. Serve the frontend over HTTPS. Browser camera access on a remote hostname requires a secure context.

For a split frontend/API deployment, set `VITE_API_BASE_URL` before `npm run build`, then list the frontend HTTPS origin in `WENT_CORS_ORIGINS`. Do not use `*` for CORS once video records are accessible remotely.

This project does not yet synchronize browser IndexedDB records across users or devices. A school-wide, multi-user deployment needs authentication, record ownership checks, PostgreSQL, and shared object storage before it should use more than one backend instance.

## Backend storage

- Default location: `WenT/backend/data/`.
- SQLite metadata and results: `data/analyses.sqlite3`.
- Original uploaded videos: `data/videos/`.
- Set `WENT_DATA_DIR` to place both in another local directory.
- The data directory is ignored by git. It can contain identifiable video and must not be exposed as a static directory.
- Deleting a record from the Records page also requests deletion of its saved backend analysis and video.
- A manual ROI retry uses the existing backend video through its `analysis_id`; it does not upload the same clip again.

## Operator workflow

1. Start the camera and drag the one box over the side-view upper body.
2. Confirm the box. The alignment latch locks quickly and releases only after sustained failure.
3. Complete preparation, tidal breathing, maximum inhale, and maximum exhale.
4. The browser immediately saves the realtime result and original recording.
5. Select offline analysis to upload the same video to the local FastAPI service.
6. Open Records to review the independent result paths, their aligned display trace, and synchronized stable-hold/Offline landmark evidence.
7. Export local SVG/CSV/JSON or request a reproducible backend ZIP after Offline analysis completes.

## Limits

`vt_px`, `vc_px`, and their frontend area equivalents are image-derived proxies. They are not litres and do not replace calibrated spirometry or clinical assessment. Video remains in browser storage until the operator deletes the local record. Once the operator starts offline analysis, a backend copy is also retained until that backend record is deleted.

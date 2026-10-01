# WenT

**Camera-based respiratory movement review with independent Realtime and Offline analysis.**


![Frontend](https://img.shields.io/badge/frontend-Vue%20%2B%20Vite-0f9d76)
![Backend](https://img.shields.io/badge/backend-FastAPI-059669)
![Status](https://img.shields.io/badge/status-local%20demo-cc7a00)

WenT turns a guided side-view camera recording into a reviewable respiratory-movement record. The browser produces an immediate Realtime waveform, the backend independently reprocesses the saved video, and the review UI aligns both paths without hiding their differences.



## What WenT does

- **Guides the operator** through preparation, positioning, ROI selection, and six timed measurement phases (37 seconds total).
- **Measures in the browser** using grayscale conversion, Otsu segmentation, subject-area tracking, filtering, peak/trough analysis, RR, `VtA`, and `VcA`.
- **Keeps a local record first** in IndexedDB, including the video when recording is available, ROI, phases, Realtime samples, metrics, and evidence timing.
- **Runs an independent Offline pipeline** with FastAPI, OpenCV, and an FFmpeg fallback for browser-recorded WebM files.
- **Explains disagreement instead of concealing it** by showing Realtime, Offline, and an aligned review-only Primary trace together.
- **Retains inspectable evidence** for stable holds and Offline landmarks such as maximum inhale and maximum exhale.
- **Exports reproducible results** as browser-side SVG/CSV/JSON or a backend ZIP containing JSON, CSV, SVG, and a human-readable manifest.

## System at a glance

![WenT system architecture](docs/architecture/WenT_Architecture_EN.png)

The architecture deliberately keeps two formal measurement paths:

| Path | Runs in | Input | Formal output |
| --- | --- | --- | --- |
| Realtime | Browser | Live frames inside the locked thorax ROI | Realtime waveform, RR, `VtA`, `VcA`, quality |
| Offline | FastAPI backend | Independently decoded saved video and the same ROI contract | Offline waveform, RR, `Vt`, `Vc`, quality, landmarks |
| Primary | Review layer | Aligned normalized Realtime and Offline samples | Display-only comparison trace |

Primary is not a third measurement algorithm. It supports visual review and never replaces formal Realtime or Offline metrics.

## From camera to review

| Step | What happens |
| --- | --- |
| Position | The operator frames the side-view upper body and locks one normalized `went-roi-v2` thorax ROI. |
| Measure | WenT records the guided phases while the browser derives a Realtime area signal. |
| Save locally | The available video, ROI, phase windows, samples, results, and evidence references are written to IndexedDB. A signal-only record can be saved when video recording is unavailable. |
| Analyze Offline | The saved recording and capture contract are submitted to FastAPI for independent decoding and analysis. |
| Align for review | WenT estimates sign and delay, then creates a normalized Primary display trace while preserving both formal results. |
| Inspect and export | Records, waveforms, evidence frames, quality information, and reproducible exports remain linked by analysis ID. |

## Install and run on a new computer

These instructions assume a new Windows 10/11 computer with no developer tools installed. Install the three tools below from their official sites, then close and reopen PowerShell so the new commands are available:

1. [Git for Windows](https://git-scm.com/install/windows). The default installer choices are sufficient.
2. [Python 3.12, 64-bit](https://www.python.org/downloads/release/python-31210/). Enable the Python launcher (`py`) during setup. Python 3.12 is the version used for the handover test.
3. [Node.js 24 LTS](https://nodejs.org/en/download). Install the regular Windows package; it includes npm. Node.js 24 is the version family used for the handover build.

Confirm each tool in a new PowerShell window:

```powershell
git --version
py -3.12 --version
node --version
npm --version
```

You also need a current Chrome, Edge, or Safari browser. A camera is needed for live capture; the code tests and an existing local record can be inspected without one. Open the private GitHub repository only after the owner gives your GitHub account access. Clone the URL shown by GitHub's **Code** button into a new folder, or extract the source ZIP supplied by the owner. The commands below assume the folder is named `WenT`.

```powershell
$repoUrl = Read-Host "Paste the private GitHub repository URL"
git clone $repoUrl WenT
cd WenT
```

If you received a ZIP, extract it and open PowerShell in the extracted `WenT` folder instead of using `git clone`. Git is still needed when you intend to send changes back.

The backend uses OpenCV first and the FFmpeg binary bundled by `imageio-ffmpeg` when a browser WebM cannot be decoded completely by OpenCV.

### 1. Install and start the backend

From the `WenT` repository root, use the virtual environment's Python directly. This also avoids PowerShell execution-policy problems with activation scripts:

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Keep this terminal running. A successful health check at [`http://127.0.0.1:8000/api/health`](http://127.0.0.1:8000/api/health) returns `"ok": true`. The first `pip install` downloads the Python dependencies and can take several minutes. FFmpeg is provided by the Python package `imageio-ffmpeg`; no separate FFmpeg installation is needed for the supported local workflow.

On macOS or Linux, install [Git](https://git-scm.com/install/), [Python 3.12](https://www.python.org/downloads/) and [Node.js 24 LTS](https://nodejs.org/en/download), then replace the Windows backend commands with:

```bash
cd backend
python3.12 -m venv .venv
.venv/bin/python -m pip install -e ".[test]"
.venv/bin/python -m pytest
.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### 2. Install and start the frontend

Open a **second** PowerShell window in the repository root. `npm ci` installs the exact versions recorded in `package-lock.json`:

```powershell
cd frontend
npm ci
npm test
npm run build
npm run dev
```

Open [`http://127.0.0.1:5174`](http://127.0.0.1:5174). The development server proxies `/api` to the backend on port `8000`. Keep both terminals running while using the application. On macOS or Linux, use the same `npm` commands in a second shell.

Expected checks: the frontend prints five `... tests passed` lines, `npm run build` ends with `built`, and the backend contains 45 tests in the documented revision. A real camera run must be checked separately on the target device.

If `py` is not found on Windows, rerun the Python installer and enable its launcher, or use the installed `python` command after confirming `python --version` reports 3.12. If `npm` or `git` is not found, reopen PowerShell after installation. If port `8000` or `5174` is busy, stop the old service before retrying; the frontend proxy assumes the backend is on `8000`. If the backend reports a missing package, verify that `pip install -e ".[test]"` completed in the new `.venv`. Do not copy a `.venv` or `node_modules` directory from another computer.

### 3. Run a measurement

1. Read the six Guide steps.
2. Open Position, frame the upper torso, and lock the ROI.
3. Follow the displayed breathing phases until recording completes.
4. Open Records to inspect the saved Realtime result.
5. Run Offline analysis when the backend is available.
6. Compare the independent traces, inspect landmark evidence, and export the result package.

## Review model

WenT uses explicit labels so reviewers can see where every result came from:

- **Realtime · processed** — filtered browser-side signal measured during capture.
- **Offline · processed** — filtered backend signal measured independently from decoded video.
- **Primary · processed** — aligned and normalized display trace used only for comparison.
- **Maximum inhale / maximum exhale** — Offline landmarks backed by decoded-video evidence frames.
- **Agreement and delay** — review diagnostics describing the relationship between retained traces.

Image-derived amplitude values are proxies. `vt_px`, `vc_px`, and their frontend area equivalents are not litres.

## API surface

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Service and decoder readiness |
| `POST` | `/api/analyze` | Upload a recording and capture contract for Offline analysis |
| `POST` | `/api/analyses/{id}/reanalyze` | Re-run analysis against the retained backend video |
| `GET` | `/api/analyses/{id}` | Read analysis status and results |
| `GET` | `/api/analyses/{id}/video` | Retrieve the retained source recording |
| `GET` | `/api/analyses/{id}/evidence/{evidence_id}` | Retrieve one evidence frame |
| `GET` | `/api/analyses/{id}/export` | Download the reproducible analysis ZIP |
| `POST` | `/api/exports/comparison` | Export a selected-analysis comparison |
| `DELETE` | `/api/analyses/{id}` | Delete one backend analysis and its retained files |

## Storage and exports

| Store | Default location | Contains |
| --- | --- | --- |
| Browser records | IndexedDB in the current browser profile | Video when available, ROI, phases, Realtime samples/results, backend link, evidence references |
| Analysis metadata | `backend/data/analyses.sqlite3` | Analysis status, request metadata, results, quality, alignment, errors |
| Binary files | `backend/data/videos/` and the configured evidence paths | Uploaded recordings and WebP evidence frames |

Set `WENT_DATA_DIR` to move the backend database and binary files to another persistent local directory. Browser IndexedDB and backend storage are separate; moving one does not move the other.

The backend analysis ZIP contains:

```text
analysis.json
analysis.csv
waveform.svg
README.txt
```

## Verification status

The documented clean-install checks ran on 28 September 2026 with Python 3.12.14; the backend suite was rerun on 29 September after its synthetic duration fixtures were corrected. Frontend tests used Node.js 22.13.1, and a production build also passed with Node.js 24.19.0. API and browser observations below are historical checks from 17 September, not a complete target-device workflow. Full details are in the separately supplied `05_WenT_Test_Record_and_Release_Readiness.docx` handover document.

| Check | Result |
| --- | --- |
| Backend test suite | **45 / 45 passed** on 29 September 2026 |
| Frontend test groups | **Five passed** on 28 September 2026 |
| Production frontend build | **Passed** — Vite 8.2.2, 1,580 modules transformed; Node.js 24.19.0 build also passed |
| API health, evidence retrieval, and ZIP export | **Historical pass** on 17 September 2026; not rerun in the clean clone |
| Desktop `1440×900` | **Preliminary viewport check** — no horizontal overflow observed |
| Tablet landscape `1366×1024` | **Preliminary viewport check** — no horizontal overflow observed |
| Tablet portrait `1024×1366` | **Open** — horizontal overflow remains |
| Phone `390×844` | **Open** — horizontal overflow remains |
| Full target-device camera-to-export workflow | **Not yet executed** (STC-01 to STC-06) |

Run the checks yourself after installation:

```powershell
# frontend
cd frontend
npm ci
npm test
npm run build

# backend
cd ../backend
.\.venv\Scripts\python.exe -m pytest
```

## Deployment boundary

The recommended first deployment is one HTTPS school server:

1. Build and serve the Vue frontend.
2. Reverse-proxy `/api` to one FastAPI process under the same origin.
3. Copy `backend/.env.remote.example` to a private environment file and configure the real frontend origin.
4. Mount `WENT_DATA_DIR` on persistent storage outside the Git checkout.
5. Set the proxy upload limit to at least `WENT_MAX_VIDEO_MB` and allow enough time for video analysis.

For a split frontend/API deployment, set `VITE_API_BASE_URL` before `npm run build` and list the frontend HTTPS origin in `WENT_CORS_ORIGINS`.

A public multi-user deployment is outside the current baseline. It first needs authenticated record ownership, authorization on every record endpoint, a shared database, shared/object storage, migrations, backups, monitoring, and operational runbooks.

## Project structure

```text
WenT/
├─ frontend/
│  ├─ src/components/        # Guide, capture, records, charts, evidence, exports
│  ├─ src/features/camera/   # Camera lifecycle, ROI and position checks
│  ├─ src/features/realtime/ # Browser signal extraction and metrics
│  ├─ src/features/offline/  # Backend API and record-analysis controller
│  └─ test/                  # Frontend regression tests
├─ backend/
│  ├─ app/api/               # FastAPI analysis routes
│  ├─ app/analysis/          # Decode, signal, metrics, fusion, evidence, export
│  ├─ app/storage.py         # SQLite and local-file persistence
│  └─ tests/                 # Backend unit and API tests
└─ docs/architecture/        # Versioned architecture source and overview image
```

## Development rules worth preserving

- Keep Realtime and Offline algorithms independent.
- Never derive formal metrics from the Primary review trace.
- Keep the original video, ROI version, phase timing, and sample timing reproducible.
- Add a regression test when fixing signal, evidence, storage, export, or alignment behavior.
- Check the real target device before declaring camera or responsive behavior complete.
- Keep generated build output, runtime databases, uploaded recordings, and local environments out of Git.

## Current roadmap

- Fix portrait-tablet and phone layout overflow.
- Complete one full physical iPad/iPhone camera acceptance run.
- Reproduce the complete setup on a second computer after the first private GitHub push.
- Add authentication, record ownership, and shared persistence before any public multi-user service.
- Add automated browser coverage for the guide-to-record and review workflows.

The typed architecture source is available at [`docs/architecture/WenT_Architecture_EN.architecture.json`](docs/architecture/WenT_Architecture_EN.architecture.json).

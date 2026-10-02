# WenT

**A web research platform for measuring respiratory movement from lateral 2D video.**

![Frontend](https://img.shields.io/badge/frontend-Vue%20%2B%20Vite-0f9d76)
![Backend](https://img.shields.io/badge/backend-FastAPI-059669)
![Status](https://img.shields.io/badge/status-research%20prototype-cc7a00)

**Contents**

- [Research motivation and objectives](#research-motivation-and-objectives)
- [What Vt and Vc mean](#what-vt-and-vc-mean)
- [Reference method and implementation](#reference-method-and-implementation)
- [Experimental workflow](#experimental-workflow)
- [System architecture](#system-architecture)
- [Prerequisites](#prerequisites)
- [Install and run WenT](#install-and-run-went)
    - [Obtain the source](#obtain-the-source)
    - [Backend terminal](#backend-terminal)
    - [Frontend terminal](#frontend-terminal)
- [Review storage and exports](#review-storage-and-exports)
- [API surface](#api-surface)
- [Project structure](#project-structure)

## Research motivation and objectives

The reference study investigates whether an ordinary camera can provide a simple, non-contact approach to observing respiratory motion, including a possible future option for people who have difficulty using a spirometer [1]. The physical observation is that breathing changes the anterior-posterior extent of the upper body. A lateral camera view makes this front-to-back motion visible as a changing silhouette. Segmenting that silhouette over time produces an image-area waveform that can be examined alongside a volume-time spirogram.

WenT turns this research procedure into an inspectable software workflow. The project has four objectives:

1. **Guide repeatable data collection:** explain the side-on posture, define a thorax region of interest (ROI), and record the breathing phases and their actual timestamps.
2. **Extract respiratory movement:** convert camera frames into a silhouette or contour signal and estimate normal-breathing amplitude, maximum-manoeuvre amplitude and respiratory rate.
3. **Support methodological comparison:** retain separate Realtime and Offline results, expose their alignment and disagreement, and link waveform landmarks to source frames.
4. **Support reproducible analysis:** preserve the available recording, ROI, segmentation settings, samples, quality reasons and exports so another researcher can examine how a result was obtained.

These are software and measurement-method objectives. Comparing the two software paths assesses consistency between implementations; comparison against a suitably controlled reference measurement is still required to establish physiological accuracy.

## What Vt and Vc mean

The physiological definitions follow respiratory measurement terminology [2]. The superscript **A** distinguishes an image-area quantity from a measured air volume.

| Symbol | Meaning | Quantity and unit | Role in WenT |
| --- | --- | --- | --- |
| Vt, conventionally V_T | **Tidal volume :** the air volume inhaled or exhaled during an ordinary breathing cycle. | Gas volume, usually L or mL. | The physiological quantity motivating the normal-breathing analysis. |
| Vc, conventionally VC | **Vital capacity :** the volume change between full inspiration and full expiration, measured at the mouth. | Gas volume, usually L or mL. | The physiological quantity motivating the maximum-inhale and maximum-exhale analysis. |
| Vt^A | Image-derived tidal amplitude: the characteristic change in the silhouette signal during normal breathing. | Pixel-area proxy. | Shown as `VtA` where used in the UI; stored as frontend `vtPx` and backend `vt_px`. |
| Vc^A | Image-derived vital amplitude: the difference between supported maximum-inhale and maximum-exhale signal levels. | Pixel-area proxy. | Shown as `VcA` where used in the UI; stored as frontend `vcPx` and backend `vc_px`. |
| R_A = Vc^A / Vt^A | Ratio of maximum-manoeuvre amplitude to normal-breathing amplitude. | Dimensionless. | Stored as `ratio`; available only when both proxy estimates pass the implemented quality checks. |
| RR | Respiratory rate estimated from the normal-breathing signal. | Breaths per minute. | Computed separately by the two analysis paths. |



The `Px`/`_px` field names refer to image-derived area or area-equivalent values: a count of foreground pixels or a sum of contour widths across rows. They do not represent litres, millilitres or calibrated physical chest area. A dimensionless amplitude ratio permits a relative comparison under a stable measurement setup, but does not establish that the image signal is proportional to air volume. Changes in posture, camera distance, clothing or segmentation can also change the ratio.

## Reference method and implementation

The following concepts are taken from the supplied reference manuscript, particularly Section 3, Figures 2-6 and Equations (1)-(4) [1]. They explain why the project uses a side-view camera and what the waveform represents.

| Research concept | Meaning in the reference method | Connection to WenT |
| --- | --- | --- |
| **Lateral 2D view** | Observe upper-body motion with a camera placed to the side. | The Guide and Position stages establish the side-on view and thorax ROI. |
| **Anterior-posterior motion** | Breathing changes the front-to-back extent of the upper body. | Silhouette and anterior-contour changes supply the movement signal. Anatomical front-to-back direction is distinct from the image coordinate labels. |
| **Maximum inhalation and exhalation** | Identify the range of silhouette change during the maximum manoeuvre. | Named capture phases constrain the search for Vc^A and its evidence frames. |
| **Grayscale image f_t(i,j)** | Represent each video frame by intensity; i is horizontal position, j is vertical position and t denotes time/frame. | The browser and backend convert the selected image region to grayscale. |
| **Binary thresholding / Otsu reference** | Separate the body from the background using an intensity threshold. | WenT uses a calibrated threshold when available, with Otsu-based estimation as a fallback, and handles dark or light foreground polarity. |
| **Body area A_t** | Count foreground pixels in each frame to obtain a temporal area signal. | WenT retains an area or contour-derived signal with timestamps and quality information. |

For the reference study's light foreground on a dark background, the binary mask and area are:

$$
B_t(i,j)=\begin{cases}1,&f_t(i,j)>\tau,\\0,&\text{otherwise},\end{cases}
\qquad
A_t=\sum_{i=0}^{I-1}\sum_{j=0}^{J-1}B_t(i,j).
$$

Here, $\tau$ is the segmentation threshold and $I$ and $J$ are the image-region width and height. The reference experiment used white T-shirts, a black background and a camera distance of 1 m to simplify segmentation [1]. Those conditions describe that experiment; they are not evidence that arbitrary lighting, clothing or camera setups have been validated in WenT.

The manuscript's amplitude definitions are:

$$
V_t^A=\frac{1}{N}\sum_{k=1}^{N}\left(a_k^{\max}-a_k^{\min}\right),
\qquad
V_c^A=A_{\max}-A_{\min},
\qquad
R_A=\frac{V_c^A}{V_t^A}.
$$

$N$ is the number of selected normal breaths; $a_k^{\max}$ and $a_k^{\min}$ are their local area extrema. The manuscript compares the image ratio $R_A$ with the corresponding spirometry ratio because the underlying measurements have different units [1].


## Experimental workflow

The operator reviews six visual Guide steps, opens Position, frames the side-view upper body and locks the normalized `went-roi-v2` ROI. The application then runs this nominal **37-second** sequence:

| Phase | Duration | Purpose |
| --- | --- | --- |
| Ready | 3 s | Establish the start of the recorded sequence. |
| Normal breathing | 12 s | Collect ordinary breathing cycles for Vt^A and RR. |
| Prepare to inhale | 3 s | Give the next manoeuvre instruction. |
| Full inhale | 8 s | Observe expansion towards the supported inhale level. |
| Prepare to exhale | 3 s | Give the next manoeuvre instruction and retain the post-inhale level. |
| Slow exhale | 8 s | Observe contraction towards the supported exhale level. |



## System architecture

![WenT system architecture](docs/architecture/WenT_Architecture_EN.png)

| Path | Execution | Input | Retained output |
| --- | --- | --- | --- |
| Realtime | Vue browser application | Live frames in the locked thorax ROI | Area/contour waveform, `vtPx`, `vcPx`, RR and quality reasons. |
| Offline | FastAPI, OpenCV and SciPy | Independently decoded saved video and capture contract | Row-profile waveform, `vt_px`, `vc_px`, RR, quality and landmarks. |
| Primary | Review layer | Aligned, scaled Realtime and Offline samples | Display trace for comparing timing and waveform shape. |

The backend first attempts OpenCV decoding and uses the FFmpeg executable provided by `imageio-ffmpeg` when needed for browser recordings. The architecture source is [WenT_Architecture_EN.architecture.json](docs/architecture/WenT_Architecture_EN.architecture.json).

## Prerequisites

Install the versions below for your operating system and CPU architecture.

| Tool | Version | Download / installation |
| --- | --- | --- |
| Git | Latest stable 2.x | [Windows](https://git-scm.com/install/windows) · [macOS](https://git-scm.com/install/mac) · [Linux](https://git-scm.com/install/linux) |
| Python | 3.12.x | [Windows / macOS installer: 3.12.10](https://www.python.org/downloads/release/python-31210/) · [Ubuntu 24.04: python3.12](https://packages.ubuntu.com/noble/python3.12) and [python3.12-venv](https://packages.ubuntu.com/noble/python3.12-venv) |
| Node.js | 24 LTS, including npm | [Windows / macOS / Linux](https://nodejs.org/en/download) |
| Browser | Latest stable Chrome | [Windows / macOS / Linux](https://www.google.com/chrome/) |

Python packages, including the video decoder, are installed by the backend command below. Frontend packages are installed from `package-lock.json` using `npm ci`.

## Install and run WenT

### Obtain the source

```sh
git clone https://github.com/D02Dar/lungde.git WenT
cd WenT
```

### Backend terminal

From the repository root, use the commands for your OS.

**Windows (PowerShell):**

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e "."
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

**macOS / Linux:**

```bash
cd backend
python3.12 -m venv .venv
.venv/bin/python -m pip install -e "."
.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Frontend terminal

Open a second terminal in the repository root:

```sh
cd frontend
npm ci
npm run dev
```

On Windows PowerShell, use `npm.cmd` if `npm.ps1` is blocked.

Keep both terminals running and open [WenT](http://127.0.0.1:5174). The backend [health endpoint](http://127.0.0.1:8000/api/health) is on port `8000`. Stop the servers with Ctrl+C.

## Review storage and exports



| Store | Default location | Contents |
| --- | --- | --- |
| Browser record | IndexedDB in the current browser profile | Available video, ROI, phases, samples/results, backend link and evidence references. |
| Backend metadata | `backend/data/analyses.sqlite3` | Status, capture metadata, results, quality, alignment and errors. |
| Backend binary files | `backend/data/videos/` and `backend/data/evidence/` | Uploaded recordings and WebP evidence frames. |

Set `WENT_DATA_DIR` to use another persistent backend data directory. Browser and backend storage are separate. Removing a local record attempts linked backend cleanup; a failed request must not be interpreted as deletion of every copy.

Browser exports support SVG, CSV and JSON. A backend single-analysis ZIP contains `analysis.json`, `analysis.csv`, `waveform.svg` and `README.txt`; source videos and evidence image binaries are not embedded in that ZIP. Selected-analysis comparison exports support summary tables and normalized traces.



## API surface

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Service and decoder readiness. |
| `POST` | `/api/analyze` | Upload a recording and capture contract for Offline analysis. |
| `POST` | `/api/analyses/{id}/reanalyze` | Reanalyse a retained backend recording. |
| `GET` | `/api/analyses/{id}` | Read status and results. |
| `GET` | `/api/analyses/{id}/video` | Retrieve the source recording. |
| `GET` | `/api/analyses/{id}/evidence/{evidence_id}` | Retrieve a linked evidence frame. |
| `GET` | `/api/analyses/{id}/export` | Download the single-analysis ZIP. |
| `POST` | `/api/exports/comparison` | Export selected analyses. |
| `DELETE` | `/api/analyses/{id}` | Remove an analysis and its retained files. |



The principal measurement limitations are 2D projection, body/posture changes, illumination and clothing contrast, motion unrelated to breathing, ROI selection and incomplete manoeuvres. Camera geometry and segmentation can affect amplitudes; values from different people or setups cannot be assumed directly comparable. Software quality checks are engineering rejection rules, and normalized trace similarity is insufficient evidence of physiological accuracy.





## Project structure

```text
WenT/
├─ frontend/
│  ├─ src/components/        # Guide, records, charts, evidence and exports
│  ├─ src/features/camera/   # Camera lifecycle, positioning and ROI contract
│  ├─ src/features/protocol/ # Guided breathing phase configuration
│  ├─ src/features/realtime/ # Browser signal extraction and metrics
│  ├─ src/features/offline/  # Backend API and stored-record analysis controller
│  └─ test/                 # Frontend regression tests
├─ backend/
│  ├─ app/api/              # Analysis, evidence and export routes
│  ├─ app/analysis/         # Decode, segmentation, metrics, quality and alignment
│  ├─ app/storage.py        # SQLite and file persistence
│  ├─ pyproject.toml        # Python package and dependency declarations
│  └─ tests/                # Backend unit and integration tests
└─ docs/architecture/       # Architecture sources and overview image
```

When changing analysis behaviour, preserve the distinction between physiological targets and image-derived proxies, keep the Realtime/Offline outputs separate, retain timing/ROI evidence, and update the relevant regression tests and research documentation. Generated environments, build output and identifiable measurement data should remain outside source control.


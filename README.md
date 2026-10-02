# WenT

**A web research platform for measuring respiratory movement from lateral 2D video.**

![Frontend](https://img.shields.io/badge/frontend-Vue%20%2B%20Vite-0f9d76)
![Backend](https://img.shields.io/badge/backend-FastAPI-059669)
![Status](https://img.shields.io/badge/status-research%20prototype-cc7a00)



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

## Prerequisites on Windows macOS and Linux

The frontend and backend can be prepared on Windows, macOS or Linux. The recorded handover verification was performed on Windows; the instructions below provide installation routes for other platforms, whose camera, codec and complete-workflow acceptance must be checked separately. Phones and tablets can be capture clients for a hosted application; they are not required to run the Python/Node development environment.

| Prerequisite | Selected version or requirement | Purpose |
| --- | --- | --- |
| Git | A current platform package. | Obtain and identify the source revision. |
| Python | **3.12 recommended**; the backend declares `>=3.11`. | Run FastAPI and the analysis packages in a project virtual environment. |
| Node.js and npm | **Node.js 24 LTS** with its bundled npm. | Install the locked frontend dependencies and run Vite. |
| Browser | A browser with camera and MediaRecorder support for the chosen workflow. | Run the capture/review client; verify the actual browser/device combination. |
| Camera and network | Camera permission for live capture; internet access for initial package downloads. | Record the experiment and install dependencies. |

Use packages matching the computer's architecture, such as Apple Silicon/ARM64 or Intel/x64. The historical backend test used Python 3.12.14, and a frontend build used Node.js 24.19.0. Installing a different patch release is a new environment that must be recorded and checked. Python 3.12.10 is the last 3.12 release with official Windows/macOS binary installers; later 3.12 security releases are source-only [Python release information](https://www.python.org/downloads/release/python-31214/).

### Windows

Install [Git for Windows](https://git-scm.com/install/windows), the appropriate [Python 3.12.10 installer](https://www.python.org/downloads/release/python-31210/) and [Node.js 24 LTS](https://nodejs.org/en/download). Enable the Python launcher and the installer's PATH option. Node's installer includes npm. Close and reopen PowerShell, then check:

```powershell
git --version
py -3.12 --version
node --version
npm --version
Get-Command git, py, node, npm
```

If `py` is unavailable, use the installed Python executable after verifying its version, or repair the launcher installation. Use the same verified interpreter to create the project environment.

### macOS

Use Terminal with its normal zsh or bash shell. Install Git through [Xcode Command Line Tools](https://git-scm.com/install/mac):

```bash
xcode-select --install
```

Install the universal2 macOS package from [Python 3.12.10](https://www.python.org/downloads/release/python-31210/) and a compatible [Node.js 24 LTS package](https://nodejs.org/en/download). Reopen Terminal and verify:

```bash
git --version
python3.12 --version
node --version
npm --version
command -v git python3.12 node npm
```

For multiple project runtimes, Python can instead be managed with [pyenv](https://github.com/pyenv/pyenv#installation), and Node with [nvm](https://github.com/nvm-sh/nvm#installing-and-updating). Complete each manager's shell setup before using its commands. Create WenT's `.venv` from the selected Python; a version manager and a virtual environment serve different purposes.

### Linux

Install Git and Python through the distribution package manager when Python 3.12 is available. For **Ubuntu 24.04**, a suitable example is:

```bash
sudo apt-get update
sudo apt-get install -y git curl python3.12 python3.12-venv
```

Other distributions have different package names and repositories; use their supported packages rather than assuming these Ubuntu commands apply. If the required Python version is unavailable, install [pyenv](https://github.com/pyenv/pyenv#installation), complete its shell setup and install its documented [Python build prerequisites](https://github.com/pyenv/pyenv/wiki#suggested-build-environment). With pyenv configured, an exact historical Python selection can be made as follows:

```bash
pyenv install 3.12.14
pyenv shell 3.12.14
python --version
```

Install Node through the official [nvm instructions](https://github.com/nvm-sh/nvm#installing-and-updating), reopen the shell, then select Node 24:

```bash
command -v nvm
nvm install 24
nvm use 24
git --version
python3.12 --version
node --version
npm --version
command -v git python3.12 node npm
```

`nvm install 24` selects the available patch release in that major version. Use `nvm install 24.19.0` and `nvm use 24.19.0` when deliberately reproducing the historical build environment. Record which patch release was actually used.

## Install and run WenT

### Obtain the source

In PowerShell on Windows or Terminal on macOS/Linux:

```sh
git clone https://github.com/D02Dar/lungde.git WenT
cd WenT
git rev-parse HEAD
```

Repository access must be granted if GitHub requests authorization. A source ZIP can also be extracted into a new folder, but retain its source revision for experiment reporting. Recreate dependencies on the receiving computer rather than copying `.venv` or `node_modules`.

### Backend terminal

From the repository root on **Windows**:

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

From the repository root on **macOS/Linux**:

```bash
cd backend
python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ".[test]"
.venv/bin/python -m pip check
.venv/bin/python -m pytest
.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

These commands use the virtual environment's interpreter directly, so activation is optional. Installing `.[test]` installs the backend runtime dependencies plus pytest/httpx. OpenCV, NumPy, SciPy and `imageio-ffmpeg` are declared in [backend/pyproject.toml](backend/pyproject.toml); FFmpeg does not normally require a separate system installation when the package provides a compatible executable. A package/decoder unavailable for the chosen OS or architecture must be resolved and checked before recording validation results.

Keep this terminal running. Open [the backend health endpoint](http://127.0.0.1:8000/api/health) and check both `ok: true` and `decoder.available: true`; a service response alone does not establish decoder readiness.

### Frontend terminal

Open a **second terminal** in the repository root. The commands are the same on all three platforms:

```sh
cd frontend
npm ci
npm test
npm run build
npm run dev
```

Open [http://127.0.0.1:5174](http://127.0.0.1:5174). The frontend proxies `/api` to the backend on port `8000`; keep both terminals running. `npm ci` uses [package-lock.json](frontend/package-lock.json) and fails if it disagrees with `package.json`, rather than silently updating the lockfile. See the [npm ci documentation](https://docs.npmjs.com/cli/v11/commands/npm-ci/).

If Windows PowerShell blocks `npm.ps1` under its execution policy, use `npm.cmd ci`, `npm.cmd test`, `npm.cmd run build` and `npm.cmd run dev` for the same steps. The backend commands above also work without running a virtual-environment activation script.

The frontend currently has five Node test groups, and the documented backend revision has 45 tests. Passing these checks does not complete a physical-camera or clinical validation run. Stop a development server with Ctrl+C in its terminal. Ports `5174` and `8000` must be free before restarting.




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


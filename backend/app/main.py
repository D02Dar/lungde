import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api.analyze import router as analyze_router


LOCAL_ORIGINS = ("http://127.0.0.1:5174", "http://localhost:5174")


def cors_origins(value: str | None = None) -> list[str]:
    """Accept a comma-separated origin allow-list without opening CORS globally."""
    configured = os.environ.get("WENT_CORS_ORIGINS", "") if value is None else value
    origins = [origin.strip().rstrip("/") for origin in configured.split(",") if origin.strip()]
    return origins or list(LOCAL_ORIGINS)


app = FastAPI(
    title="WenT Respiratory Analysis",
    version="0.1.0",
    description="offline offline RGB analysis. Outputs are image-derived proxies, not clinical spirometry.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)
app.include_router(analyze_router, prefix="/api")


@app.get("/api/health")
def health():
    try:
        import imageio_ffmpeg
        decoder = {"available": True, "path": imageio_ffmpeg.get_ffmpeg_exe()}
    except Exception:
        decoder = {"available": False, "path": None}
    return {
        "ok": True,
        "service": "went-offline",
        "algorithmVersion": "offline-rgb-v1",
        "storage": "sqlite-and-local-video",
        "decoder": decoder,
    }

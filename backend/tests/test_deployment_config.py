from app.api.analyze import max_video_bytes
from app.main import LOCAL_ORIGINS, cors_origins


def test_cors_defaults_to_local_only_and_accepts_school_allow_list():
    assert cors_origins("") == list(LOCAL_ORIGINS)
    assert cors_origins("https://app.school.test/, https://research.school.test") == [
        "https://app.school.test", "https://research.school.test",
    ]


def test_upload_limit_has_safe_default_and_bounded_remote_override():
    assert max_video_bytes("bad") == 250 * 1024 * 1024
    assert max_video_bytes("64") == 64 * 1024 * 1024
    assert max_video_bytes("0") == 1 * 1024 * 1024
    assert max_video_bytes("9999") == 1024 * 1024 * 1024

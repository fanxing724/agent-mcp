"""Catalog is static: platform discovery endpoints require a login JWT."""

TTS_MODELS = ("qwen-audio-3.0-tts-flash", "qwen-audio-3.0-tts-plus")
IMAGE_MODEL = "qwen-image-3.0"
ASR_MODEL = "qwen-audio-3.0-asr-flash"
VIDEO_MODELS = (
    "happyhorse-1.1-t2v",
    "happyhorse-1.1-i2v",
    "happyhorse-1.1-r2v",
    "wan3.0-video",
)
EDIT_MODEL = "happyhorse-1.0-video-edit"
MODELS = [
    *[{"id": m, "capability": "tts"} for m in TTS_MODELS],
    {"id": IMAGE_MODEL, "capability": "image", "modes": ["text_to_image", "image_edit"]},
    {"id": ASR_MODEL, "capability": "asr"},
    *[{"id": m, "capability": "video"} for m in VIDEO_MODELS],
    {"id": EDIT_MODEL, "capability": "video_edit"},
]


def list_models(capability: str | None = None) -> dict:
    valid = {m["capability"] for m in MODELS}
    if capability is not None and capability not in valid:
        raise ValueError(f"capability must be one of {sorted(valid)}")
    return {
        "models": [
            dict(m, verification="see_docs/live-validation.md")
            for m in MODELS
            if capability is None or m["capability"] == capability
        ],
        "notes": "Model IDs from supplied AgentScope guide; see docs/live-validation.md for live results. "
        "Wan text-to-video mapping has passed one live smoke test. No account/JWT APIs are used.",
    }

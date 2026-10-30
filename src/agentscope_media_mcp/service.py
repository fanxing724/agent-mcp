"""Typed product operations mapped to DashScope-native media requests."""

import base64
import binascii
import re
from urllib.parse import urlsplit

from .catalog import ASR_MODEL, EDIT_MODEL, IMAGE_MODEL, TTS_MODELS, VIDEO_MODELS
from .client import MediaClient, MediaError

MULTIMODAL = "/services/aigc/multimodal-generation/generation"
VIDEO = "/services/aigc/video-generation/video-synthesis"
TTS = "/services/audio/tts/SpeechSynthesizer"


def text(value: str) -> str:
    if not value.strip():
        raise ValueError("Text/prompt cannot be empty")
    return value


def media_url(value: str) -> str:
    url = urlsplit(value)
    if url.scheme not in ("https", "http") or not url.hostname or url.username or url.password:
        raise ValueError("Media must be a public HTTP(S) URL without embedded credentials")
    return value


def compact(**kwargs) -> dict:
    return {k: v for k, v in kwargs.items() if v is not None}


def normalize(data: dict, model: str | None = None) -> dict:
    output = data.get("output", {})
    if not isinstance(output, dict):
        raise MediaError("invalid_response", "Expected output object")
    raw_status = output.get("task_status")
    states = {
        "PENDING": "pending",
        "RUNNING": "running",
        "SUCCEEDED": "succeeded",
        "FAILED": "failed",
        "CANCELED": "canceled",
        "CANCELLED": "canceled",
        "UNKNOWN": "unknown",
    }
    assets, texts = [], []

    def add(kind, url):
        if isinstance(url, str) and url.startswith(("https://", "http://")):
            asset = {"type": kind, "url": url, "expires_at": None}
            if asset not in assets:
                assets.append(asset)

    add("video", output.get("video_url"))
    add("image", output.get("image_url"))
    audio = output.get("audio")
    if isinstance(audio, dict):
        add("audio", audio.get("url"))
    for choice in output.get("choices", []):
        for item in choice.get("message", {}).get("content", []):
            if not isinstance(item, dict):
                continue
            for kind in ("image", "audio", "video"):
                value = item.get(kind)
                add(kind, value.get("url") if isinstance(value, dict) else value)
            if isinstance(item.get("text"), str):
                texts.append(item["text"])
    if isinstance(output.get("text"), str):
        texts.append(output["text"])
    task_id = output.get("task_id")
    status = (
        states.get(str(raw_status).upper(), "unknown")
        if raw_status
        else ("pending" if task_id else "succeeded" if assets or texts else "unknown")
    )
    result = {
        "model": model or data.get("model"),
        "status": status,
        "upstream_status": raw_status,
        "task_id": task_id,
        "assets": assets,
        "request_id": data.get("request_id"),
        "text": "\n".join(texts) or None,
    }
    if status in ("failed", "canceled"):
        result["error"] = {
            "code": output.get("code", status),
            "message": "Upstream task did not complete successfully",
        }
    if status == "unknown":
        result["note"] = "No recognized result or task state; gateway response needs inspection."
    return result


class MediaService:
    def __init__(self, client: MediaClient):
        self.client = client

    async def synthesize_speech(
        self,
        text_input: str,
        voice: str,
        model: str = TTS_MODELS[0],
        format: str | None = None,
        sample_rate: int | None = None,
        instruction: str | None = None,
    ) -> dict:
        if model not in TTS_MODELS:
            raise ValueError("Unsupported TTS model")
        if format is not None and format not in ("mp3", "wav", "pcm", "opus"):
            raise ValueError("format must be mp3, wav, pcm, or opus")
        if sample_rate is not None and sample_rate not in (
            8000,
            12000,
            16000,
            22050,
            24000,
            44100,
            48000,
        ):
            raise ValueError("Unsupported sample_rate")
        if format == "opus" and sample_rate in (22050, 44100):
            raise ValueError("Opus does not support this sample_rate")
        body = {
            "model": model,
            "input": compact(
                text=text(text_input),
                voice=text(voice),
                format=format,
                sample_rate=sample_rate,
                instruction=instruction,
            ),
        }
        return normalize(await self.client.request("POST", TTS, body), model)

    async def image(
        self,
        prompt: str,
        image_urls: list[str] | None = None,
        size: str | None = None,
        seed: int | None = None,
        negative_prompt: str | None = None,
    ) -> dict:
        if size is not None and not re.fullmatch(r"[1-9]\d{1,4}\*[1-9]\d{1,4}", size):
            raise ValueError("size must use width*height, e.g. 1024*1024")
        if seed is not None and not 0 <= seed <= 2147483647:
            raise ValueError("seed outside [0, 2147483647]")
        content = [{"image": media_url(u)} for u in (image_urls or [])]
        content.append({"text": text(prompt)})
        body = {
            "model": IMAGE_MODEL,
            "input": {"messages": [{"role": "user", "content": content}]},
            "parameters": compact(size=size, seed=seed, negative_prompt=negative_prompt),
        }
        return normalize(await self.client.request("POST", MULTIMODAL, body), IMAGE_MODEL)

    async def transcribe_audio(
        self, audio_url: str, language: str | None = None, enable_itn: bool = False
    ) -> dict:
        body = {
            "model": ASR_MODEL,
            "input": {"messages": [{"role": "user", "content": [{"audio": media_url(audio_url)}]}]},
            "parameters": {"asr_options": compact(language=language, enable_itn=enable_itn)},
        }
        return normalize(await self.client.request("POST", MULTIMODAL, body), ASR_MODEL)

    async def generate_video(
        self,
        model: str,
        prompt: str,
        image_url: str | None = None,
        reference_urls: list[str] | None = None,
        resolution: str | None = None,
        duration: int | None = None,
        ratio: str | None = None,
        seed: int | None = None,
    ) -> dict:
        if model not in VIDEO_MODELS:
            raise ValueError("Unsupported video generation model")
        inp = {"prompt": text(prompt)}
        refs = reference_urls or []
        if model.endswith("-i2v"):
            if not image_url or refs:
                raise ValueError("i2v requires one image_url and no reference_urls")
            if ratio:
                raise ValueError("i2v aspect ratio follows its first-frame image")
            inp["media"] = [{"type": "first_frame", "url": media_url(image_url)}]
        elif model.endswith("-r2v"):
            if image_url or not 1 <= len(refs) <= 9:
                raise ValueError("r2v requires 1–9 reference_urls and no image_url")
            inp["media"] = [{"type": "reference_image", "url": media_url(u)} for u in refs]
        elif image_url or refs:
            raise ValueError("This model currently accepts text input only")
        if duration is not None and (isinstance(duration, bool) or not 3 <= duration <= 15):
            raise ValueError("duration must be an integer in [3, 15]")
        if ratio is not None and ratio not in (
            "16:9",
            "9:16",
            "1:1",
            "4:3",
            "3:4",
            "4:5",
            "5:4",
            "9:21",
            "21:9",
        ):
            raise ValueError("Unsupported ratio")
        self._video_options(resolution, seed)
        parameters = compact(resolution=resolution, duration=duration, ratio=ratio, seed=seed)
        result = normalize(
            await self.client.request(
                "POST",
                VIDEO,
                {"model": model, "input": inp, "parameters": parameters},
                asynchronous=True,
            ),
            model,
        )
        if model == "wan3.0-video":
            result["warning"] = "Wan mapping is provisional; AgentScope live verification pending"
        return result

    @staticmethod
    def _video_options(resolution, seed):
        if resolution is not None and resolution not in ("480P", "720P", "1080P"):
            raise ValueError("resolution must be 480P, 720P, or 1080P")
        if seed is not None and not 0 <= seed <= 2147483647:
            raise ValueError("seed outside [0, 2147483647]")

    async def edit_video(
        self,
        video_url: str,
        prompt: str,
        reference_urls: list[str] | None = None,
        resolution: str | None = None,
        seed: int | None = None,
    ) -> dict:
        refs = reference_urls or []
        if len(refs) > 5:
            raise ValueError("Video editing accepts at most 5 reference images")
        self._video_options(resolution, seed)
        media = [{"type": "video", "url": media_url(video_url)}]
        media.extend({"type": "reference_image", "url": media_url(u)} for u in refs)
        body = {
            "model": EDIT_MODEL,
            "input": {"prompt": text(prompt), "media": media},
            "parameters": compact(resolution=resolution, seed=seed),
        }
        return normalize(
            await self.client.request("POST", VIDEO, body, asynchronous=True), EDIT_MODEL
        )

    async def get_task(self, task_id: str) -> dict:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,200}", task_id):
            raise ValueError("Invalid task_id")
        data = await self.client.request("GET", "/tasks/" + task_id)
        result = normalize(data)
        result["task_id"] = result["task_id"] or task_id
        return result

    async def upload_media(self, data_url: str) -> dict:
        limit = self.client.settings.upload_max_bytes
        if len(data_url) > 4 * ((limit + 2) // 3) + 100:
            raise ValueError("Upload exceeds configured size limit")
        match = re.fullmatch(
            r"data:((?:image|audio|video)/[\w.+-]+);base64,([A-Za-z0-9+/=]+)", data_url
        )
        if not match:
            raise ValueError("Expected a base64 image/audio/video data URL")
        try:
            decoded = base64.b64decode(match[2], validate=True)
        except binascii.Error:
            raise ValueError("Invalid base64 encoding") from None
        if not decoded or len(decoded) > limit:
            raise ValueError("Upload is empty or exceeds configured size limit")
        data = await self.client.request("POST", "/uploads", {"data": data_url})
        items = data.get("items")
        if not isinstance(items, list) or not items:
            raise MediaError("invalid_response", "Upload response did not contain media items")
        return {
            "items": [
                {"url": media_url(i["url"]), "mime": i.get("mime"), "bytes": i.get("bytes")}
                for i in items
            ],
            "request_id": data.get("request_id"),
        }

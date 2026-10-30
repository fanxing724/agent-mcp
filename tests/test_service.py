import json

import httpx
import pytest

from agentscope_media_mcp.catalog import list_models
from agentscope_media_mcp.client import MediaClient, MediaError
from agentscope_media_mcp.config import Settings
from agentscope_media_mcp.service import MediaService, normalize


@pytest.fixture
async def backend():
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(200, json={"output": {"task_id": "job-1", "task_status": "PENDING"}})

    client = MediaClient(Settings(api_key="test-only"), httpx.MockTransport(handle))
    yield MediaService(client), requests
    await client.close()


async def test_all_video_models_and_media_mapping(backend):
    svc, requests = backend
    for model in ("happyhorse-1.1-t2v", "wan3.0-video"):
        assert (await svc.generate_video(model, "A blue sky"))["task_id"] == "job-1"
    await svc.generate_video("happyhorse-1.1-i2v", "Move", image_url="https://example.com/a.png")
    await svc.generate_video(
        "happyhorse-1.1-r2v", "Move [Image 1]", reference_urls=["https://example.com/a.png"]
    )
    await svc.edit_video("https://example.com/a.mp4", "Turn to watercolor")
    bodies = [json.loads(r.content) for r in requests]
    assert bodies[2]["input"]["media"][0]["type"] == "first_frame"
    assert bodies[3]["input"]["media"][0]["type"] == "reference_image"
    assert bodies[4]["input"]["media"][0]["type"] == "video"
    assert all(r.headers["X-DashScope-Async"] == "enable" for r in requests)
    assert all(r.headers["Authorization"] == "Bearer test-only" for r in requests)


async def test_speech_image_asr_mapping(backend):
    svc, requests = backend
    for model in ("qwen-audio-3.0-tts-flash", "qwen-audio-3.0-tts-plus"):
        await svc.synthesize_speech("你好", "voice-from-provider", model, "wav", 24000)
    await svc.image("A tree", size="1024*1024")
    await svc.image("Make blue", ["https://example.com/a.png"])
    await svc.transcribe_audio("https://example.com/a.wav", "zh", True)
    bodies = [json.loads(r.content) for r in requests]
    assert bodies[0]["input"]["format"] == "wav"
    assert bodies[1]["model"] == "qwen-audio-3.0-tts-plus"
    assert bodies[2]["parameters"] == {"size": "1024*1024"}
    assert bodies[3]["input"]["messages"][0]["content"][0] == {"image": "https://example.com/a.png"}
    assert bodies[4]["parameters"]["asr_options"] == {"language": "zh", "enable_itn": True}


async def test_invalid_input_never_reaches_network(backend):
    svc, requests = backend
    with pytest.raises(ValueError):
        await svc.generate_video("happyhorse-1.1-i2v", "Move")
    with pytest.raises(ValueError):
        await svc.get_task("../users/me/model-api-key")
    with pytest.raises(ValueError):
        await svc.image("a", ["file:///etc/passwd"])
    with pytest.raises(ValueError):
        await svc.upload_media("data:image/png;base64,===")
    assert not requests


async def test_post_timeout_is_not_retried():
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout("do not expose request", request=request)

    client = MediaClient(Settings(api_key="secret"), httpx.MockTransport(handler))
    with pytest.raises(MediaError) as exc:
        await client.request("POST", "/uploads", {"data": "x"})
    assert exc.value.details["code"] == "submission_unknown"
    assert not exc.value.details["retryable"]
    assert len(calls) == 1
    await client.close()


async def test_redirect_never_receives_credentials():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(307, headers={"location": "https://other.example/steal"}, json={})

    client = MediaClient(Settings(api_key="secret"), httpx.MockTransport(handler))
    with pytest.raises(MediaError):
        await client.request("POST", "/uploads", {})
    assert len(calls) == 1
    await client.close()


async def test_missing_key_and_error_redaction():
    client = MediaClient(Settings())
    with pytest.raises(MediaError, match="configuration_missing"):
        await client.request("POST", "/uploads", {})
    await client.close()
    client = MediaClient(
        Settings(api_key="private-key"),
        httpx.MockTransport(
            lambda r: httpx.Response(401, json={"code": "private-key", "message": "user content"})
        ),
    )
    with pytest.raises(MediaError) as exc:
        await client.request("POST", "/uploads", {})
    assert "private-key" not in str(exc.value)
    assert "user content" not in str(exc.value)
    await client.close()


def test_catalog_and_result_states():
    assert len(list_models()["models"]) == 9
    assert len(list_models("tts")["models"]) == 2
    assert normalize({"output": {"task_status": "UNKNOWN"}})["status"] == "unknown"
    assert normalize({"output": {"task_status": "FAILED", "code": "failure"}})["error"]
    assert normalize({"output": {}})["status"] == "unknown"
    result = normalize(
        {
            "output": {
                "choices": [
                    {
                        "message": {
                            "content": [
                                {"image": "https://example.com/a.png"},
                                {"text": "recognized"},
                            ]
                        }
                    }
                ]
            }
        }
    )
    assert result["status"] == "succeeded"
    assert result["assets"][0]["type"] == "image"
    assert result["text"] == "recognized"


async def test_upload_and_query_results():
    calls = []

    def handle(request):
        calls.append(request)
        if request.method == "POST":
            return httpx.Response(
                200,
                json={
                    "items": [
                        {"url": "https://example.com/audio.wav", "mime": "audio/wav", "bytes": 3}
                    ]
                },
            )
        return httpx.Response(
            200,
            json={
                "output": {
                    "task_status": "SUCCEEDED",
                    "video_url": "https://example.com/result.mp4",
                }
            },
        )

    client = MediaClient(Settings(api_key="test"), httpx.MockTransport(handle))
    svc = MediaService(client)
    uploaded = await svc.upload_media("data:audio/wav;base64,YWJj")
    assert uploaded["items"][0]["bytes"] == 3
    result = await svc.get_task("saved-task-123")
    assert result["task_id"] == "saved-task-123"
    assert result["status"] == "succeeded"
    assert result["assets"][0]["type"] == "video"
    assert calls[1].url.path == "/api/v1/tasks/saved-task-123"
    await client.close()

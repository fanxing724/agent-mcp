"""Deployment-owned settings. Never supplied through tool arguments."""

import os
from dataclasses import dataclass, field
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Settings:
    api_key: str = field(default="", repr=False)
    base_url: str = "https://platform.agentscope.io/api/v1"
    concurrency: int = 4
    connect_timeout: float = 15
    read_timeout: float = 180
    upload_max_bytes: int = 10 * 1024 * 1024

    def __post_init__(self):
        url = urlsplit(self.base_url)
        if url.scheme != "https" or not url.hostname or url.username or url.password:
            raise ValueError("Media base URL must be HTTPS without embedded credentials")
        if url.query or url.fragment:
            raise ValueError("Media base URL cannot contain query or fragment")
        if self.concurrency < 1 or self.upload_max_bytes < 1:
            raise ValueError("Concurrency and upload limit must be positive")
        if self.connect_timeout <= 0 or self.read_timeout <= 0:
            raise ValueError("Timeouts must be positive")

    @classmethod
    def from_env(cls):
        return cls(
            api_key=os.getenv("AGENTSCOPE_API_KEY", ""),
            base_url=os.getenv("AGENTSCOPE_MEDIA_BASE_URL", cls.base_url).rstrip("/"),
            concurrency=int(os.getenv("AGENTSCOPE_HTTP_CONCURRENCY", "4")),
            connect_timeout=float(os.getenv("AGENTSCOPE_CONNECT_TIMEOUT", "15")),
            read_timeout=float(os.getenv("AGENTSCOPE_READ_TIMEOUT", "180")),
            upload_max_bytes=int(os.getenv("AGENTSCOPE_UPLOAD_MAX_BYTES", "10485760")),
        )

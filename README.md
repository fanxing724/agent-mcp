# AgentScope Media MCP

Python MCP 服务：通过 AgentScope Platform 调用语音、图片、ASR 和视频模型。无网页、无本地模型、无账户 JWT 接口。

**状态：开发版本。已开始真实接口联调，逐项结果见 [验证记录](docs/live-validation.md)。PyPI 尚未发布。**

## 本地启动

安装 uv 后，在项目目录运行：

```bash
uv sync --locked
uv run agentscope-media-mcp
```

stdio 服务由 MCP 客户端启动；直接在终端运行时等待协议输入属于正常行为。
密钥通过启动进程的 `AGENTSCOPE_API_KEY` 环境变量提供，不要写进源码。
未填写密钥仍可以初始化和列出工具，调用媒体接口时会返回配置错误。

本地客户端配置：

```json
{
  "mcpServers": {
    "agentscope-media": {
      "command": "uv",
      "args": ["--directory", "/home/fanxing/repos/agentscope-media-mcp", "run", "--locked", "agentscope-media-mcp"],
      "env": {"AGENTSCOPE_API_KEY": "<填写模型API Key>"}
    }
  }
}
```

## 模型与工具

| 工具 | 模型/功能 |
| --- | --- |
| list_models | 九个模型的静态清单，可按能力筛选 |
| synthesize_speech | qwen-audio-3.0-tts-flash / qwen-audio-3.0-tts-plus |
| generate_image / edit_image | qwen-image-3.0 |
| transcribe_audio | qwen-audio-3.0-asr-flash |
| generate_video | happyhorse-1.1-t2v / i2v / r2v、wan3.0-video |
| edit_video | happyhorse-1.0-video-edit |
| upload_media | 将 base64 data URL 上传到平台 |
| get_task | 根据上游 task_id 查询结果 |

TTS 必须指定该模型支持的 voice，避免猜测音色。Wan 暂采用原生文本输入结构，详细规格待平台确认。
480P、720P、1080P 可作为视频分辨率输入；实际可用性以具体模型和网关验证为准。
图片尺寸使用 `1024*1024` 形式，不保证任意尺寸都被模型接受。

## 调用流程

- 配音：选择 Flash 或 Plus，填写文本和有效 voice ID，调用 synthesize_speech。
- 图生视频：先取得公共图片 URL，再指定 happyhorse-1.1-i2v 和 image_url。
- 参考生视频：指定 happyhorse-1.1-r2v 和 reference_urls，可在提示词中引用 [Image 1]。
- 视频任务提交后保存 task_id，间隔查询 get_task，直到成功或失败。
- 图片、音频结果直接返回媒体 URL 或文本；如果上游返回任务，则保留任务编号。

服务不下载任意 URL，不读取调用者电脑上的路径，不永久保存作品。
API 返回链接可能过期，需要由调用者及时保存。
生成 POST 请求不自动重试；submission_unknown 表示受理结果不明，不应盲目重复生成。

## 配置

| 环境变量 | 默认值 |
| --- | --- |
| AGENTSCOPE_API_KEY | 无；生成请求必需 |
| AGENTSCOPE_MEDIA_BASE_URL | https://platform.agentscope.io/api/v1 |
| AGENTSCOPE_HTTP_CONCURRENCY | 4 |
| AGENTSCOPE_CONNECT_TIMEOUT | 15 秒 |
| AGENTSCOPE_READ_TIMEOUT | 180 秒 |
| AGENTSCOPE_UPLOAD_MAX_BYTES | 10485760（10 MiB） |

并发限制是同时进行的 HTTP 请求数，不是上游运行中的视频任务数。
不连接 Credits、定价和用户信息接口，无费用审批。
媒体 HTTP 客户端使用直连，不继承本机代理变量；不会修改系统或其他应用的网络配置。

## 测试和打包

```bash
uv sync --locked --group dev
uv run pytest
uv run ruff check .
uv build
uv run python scripts/check_wheel.py
```

## 魔搭部署

可先从 GitHub 安装，选择 uvx 配置；建议将 `main` 换成经过验证的提交号固定版本：

```json
{
  "mcpServers": {
    "agentscope-media": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/fanxing724/agent-mcp.git@main", "agentscope-media-mcp"],
      "env": {"AGENTSCOPE_API_KEY": "<部署时填写>"}
    }
  }
}
```

魔搭托管运行 stdio 进程并提供远程连接，程序本身不监听 HTTP 端口。
平台的密钥填写和托管限制需实际部署验证。

请求字段参考及验证边界见 [接口说明](docs/api-notes.md)。

# 真实接口联调

日期：2026-10-30。仅使用专用模型 API Key，不使用登录 JWT。

| 模型/能力 | 当前结果 |
| --- | --- |
| TTS Flash | longanfengyue 音色生成成功 |
| TTS Plus | longanlingxin 音色生成成功；音频下载成功，ffprobe 解析为 WAV，2.8 秒 |
| qwen-image-3.0 文生图 | 返回图片成功 |
| qwen-image-3.0 图生图 | 返回修改后的图片成功 |
| HappyHorse t2v | 480P、3 秒任务完成；下载并解析为 MP4、848×480、3.16 秒 |
| HappyHorse i2v | 480P、3 秒任务已完成，返回视频 |
| HappyHorse r2v | 480P、3 秒任务已完成，返回视频 |
| wan3.0-video | 720P、5 秒任务已完成，返回视频 |
| HappyHorse video-edit | 480P 被上游拒绝，已限制为 720P/1080P；720P 复测已成功 |
| ASR | 返回 HTTP 502 / ASP.UPSTREAM.ERROR；网关报告上游原生接口返回 400，尚未跑通 |
| 上传 | 使用 TTS 生成的音频上传成功 |

状态仅代表表内请求，不代表所有分辨率、音色、格式均已验证。
ASR 需要继续核对网关使用的型号及参数，不能标记为已可用。
生成作品、完整响应、密钥和远程专用连接保存在本机仓库外，不纳入版本管理。

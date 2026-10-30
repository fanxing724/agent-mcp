# 接口依据与验证边界

生产路径与模型 ID 来自用户提供的 AgentScope Platform 指南；此指南声明媒体请求遵循 DashScope 原生结构。
适配器参照下列官方文档，但对应 AgentScope 型号尚未实测，不能将上游可用性等同网关兼容性：

- [TTS HTTP](https://www.alibabacloud.com/help/en/model-studio/qwen-audio-tts-http-api)：input.text、voice、format、sample_rate、instruction。当前官方示例使用 3.1 型号，3.0 兼容性待验证。
- [Qwen Image](https://docs.bailian.console.aliyun.com/en/model-studio/qwen-image-api)：input.messages[].content；parameters.size。
- [Qwen ASR](https://help.aliyun.com/en/model-studio/qwen-asr-api-reference)：多模态消息音频输入与 parameters.asr_options。
- [HappyHorse t2v](https://help.aliyun.com/en/model-studio/happyhorse-text-to-video-api-reference)：prompt、resolution、ratio、duration、seed。
- [HappyHorse i2v](https://help.aliyun.com/en/model-studio/happyhorse-image-to-video-api-reference)：media 中 type=first_frame。
- [HappyHorse r2v](https://help.aliyun.com/en/model-studio/happyhorse-reference-to-video-api-reference)：media 中 type=reference_image。
- [HappyHorse 编辑](https://help.aliyun.com/en/model-studio/happyhorse-video-edit-api-reference)：一个 type=video、最多五个 reference_image；不暴露无法自由控制的 duration。

视频请求带 X-DashScope-Async: enable。任务状态来自 output.task_status。
未沿用 Chat 专属的幂等头，也不猜测取消任务接口。

## 尚待验证

所有九个模型的真实调用，特别是 TTS 音色、qwen-image-3.0 参数以及 wan3.0-video 的完整结构与输入模式。
上传限制、托管输入大小和媒体结果有效期也需要实测。
首版不提供批量图片数量参数，直到确认 qwen-image-3.0 的支持范围。

## 发布前验收

本地协议、请求映射、错误处理测试 → 真实模型调用与作品检查 → wheel/sdist 干净安装 → PyPI 发布 → 魔搭外部连接。
每一步分别记录。没有 Key 不运行真实生成测试，不访问已有其他应用配置中的密钥。

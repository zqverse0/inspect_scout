# scout-lite 与上游的对应

基线：inspect_scout `7521262`（本 fork 的 main），inspect_ai `0.3.287.dev30`（基线记录在 `tests/golden/VERSION`）。

scout-lite 只做一件事：对**一个已加载的会话**跑 scout 的扫描器。分析代码摘自 scout，模型层换成只支持
OpenAI 兼容接口的薄替身。原则是**能复制就不改写**：改动只限导入路径和删掉单会话走不到的分支。

## 文件对应

| scout-lite | 来源 | 改动 |
|---|---|---|
| `_llm_scanner/prompt.py`、`types.py` | `src/inspect_scout/_llm_scanner/` 同名 | 只改导入 |
| `_llm_scanner/answer.py`、`generate.py`、`structured.py`、`_reducer.py` | 同上 | 只改导入 |
| `_llm_scanner/_llm_scanner.py` | 同上 | 去掉流式句柄、时间线、事件分支 |
| `_scanner/extract.py` | `_scanner/extract.py` | 只改导入 |
| `_scanner/result.py`、`util.py` | `_scanner/result.py`、`util.py` | 只保留 `Result`、`as_resultset`、`_message_id` |
| `_scanner/scanner.py` | `_scanner/scanner.py` | 替身：`@scanner` 不登记，原样返回 |
| `_transcript/messages.py` | `_transcript/messages.py` | 只保留消息分段（`segment_messages`、`transcript_messages` 的消息分支） |
| `_transcript/types.py` | `_transcript/types.py` | 只有消息的 `Transcript`，字段名不变 |
| `_util/refusal.py`、`jinja.py` | `_util/` 同名 | 只改导入 |
| `_grep_scanner/` | `_grep_scanner/` | 去掉事件匹配 |
| `_ai/_json.py`、`_tool_params.py`、`_text.py`、`_unicode.py` | inspect_ai `util/_json.py`、`tool/_tool_params.py`、`_util/text.py`、`scorer/_unicode.py` | 整文件复制 |
| `_ai/_number.py`、`_model_info.py` | inspect_ai `scorer/_common.py`、`_util/pattern.py`、`model/_model_info.py` | 按函数复制 |
| `_ai/_model_info.json` | inspect_ai 解析后的模型资料库 | 冻结为「名字 → 输入 token 上限」 |
| `_ai/model.py`、`tool.py`、`util.py` | inspect_ai 模型 / 工具层 | **自写替身**，规则出处见注释 |
| `berth.py`、`cli.py` | — | 自写：读 Berth 会话、问题配置 → 扫描器 |

## 怎么证明一致

`tests/golden/` 是用真 inspect_scout 录下的「发出的每个请求 + 最终结果」，覆盖各答案类型、解析失败重问、
拒答重试、推理内容回传、结构化与多条结果、工具参数校验失败、过滤工具内容、长会话分段（任一为是 / LLM 合并）、
关键词扫描，以及模型资料库查找。`tests/test_oracle.py` 要求 scout-lite 逐字段相同。

## 同步上游

1. fork 的 main 跟上上游；在装有 inspect_scout 的环境里 `python tests/record_golden.py` 重录 golden。
2. 对照上表，把来源文件的改动合进对应文件（只改导入的文件可以整文件替换后重新改导入）。
3. `pytest`：全部通过即一致。不通过时看哪个请求不同，多半是替身要跟着上游的序列化规则改。

## 已知不支持（`ponytail:` 注释标出）

- 只有 OpenAI 兼容服务（`openai-api/<服务>/<模型>`）；正文里的 `<think>` 标签与 OpenRouter `reasoning_details` 不解析。
- 工具参数不是 JSON 时不做 YAML 兜底；不检查参数嵌套深度。
- HTTP 重试只按 429 / 5xx / 网络错误做指数退避。

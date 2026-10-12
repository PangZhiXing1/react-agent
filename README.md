# react-agent

ReAct 模式的 AI Agent 教学示例：模型按「思考 → 行动 → 观察」循环，调用文件读写与终端命令工具，在指定工作区内完成任务。单线程同步运行，模型输出在终端流式打印。

## 环境

Python 3.10+，依赖只有 `openai`：

```bash
pip install -r requirements.txt
```

## 配置

改 `config.py` 即可，不需要环境变量：

| 常量 | 说明 |
|---|---|
| `API_KEY` | 模型服务鉴权 |
| `BASE_URL` | 接口地址（智谱、OpenRouter 等 OpenAI 兼容接口均可） |
| `MODEL` | 模型名称 |
| `WORKSPACE` | Agent 的工作区目录：读写文件、执行命令都在这里。已解析为绝对路径（相对路径以本项目目录为基准），目录不存在会直接报错退出 |

## 运行

双击 `start.bat`，或：

```bash
py main.py
```

- 启动后可**连续输入任务**，直接回车即退出
- 任务之间**共享对话上下文**；每次请求前会把发给模型的完整内容打印在终端
- 执行终端命令前会先问 `是否继续？（Y/N）`
- 模型回复里若没有完整的 `<action>` 或 `<final_answer>` 标签，会被丢弃并重新请求
- 两个护栏：对话历史超过 200 条丢弃最早的（`agent.py` 的 `MAX_MESSAGES`）；单条命令输出超过 2000 字符截断（`tools.py` 的 `MAX_OUTPUT_CHARS`）

## 文件

| 文件 | 职责 |
|---|---|
| `main.py` | 入口：校验工作区、组装系统提示词、连续输入任务的循环 |
| `config.py` | 配置：API Key / Base URL / 模型名 / 工作区 |
| `prompts.py` | 系统提示词模板（XML 标签协议 + 一个真实工具示例） |
| `tools.py` | 三个工具：`read_file` / `write_to_file` / `run_terminal_command`；docstring 含调用示例，会被注入提示词 |
| `agent.py` | ReAct 主循环、流式请求与合法性重试、标签与参数解析、上下文护栏 |
| `start.bat` | 一键启动脚本（内容保持纯 ASCII，勿在其中加中文） |

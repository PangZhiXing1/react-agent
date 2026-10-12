"""模型配置与工作区配置：直接写在下面。

切换服务商、模型或工作区只改这里，不依赖任何环境变量。
"""
import os

API_KEY = ""
BASE_URL = "https://api.siliconflow.cn/v1"
MODEL = "deepseek-ai/DeepSeek-R1-0528-Qwen3-8B"

# Agent 的工作区：读写文件、执行命令都在这个目录里进行。
# 相对路径以本项目目录为基准，这里已解析成绝对路径，供 agent 直接使用。
# 换工作区只改最后那个目录名即可，也可以直接写绝对路径。
WORKSPACE = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "test"))

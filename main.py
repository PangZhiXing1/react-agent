"""命令行入口：python main.py"""
import inspect
import os
import sys
from string import Template

from agent import ReActAgent
from config import WORKSPACE
from prompts import react_system_prompt_template
from tools import read_file, run_terminal_command, write_to_file

TOOLS = [read_file, write_to_file, run_terminal_command]


def build_system_prompt(tools, workspace):
    """把工具清单与工作区路径填进提示词模板。"""
    tool_list = "\n".join(
        f"- {func.__name__}{inspect.signature(func)}: {inspect.getdoc(func)}" for func in tools
    )
    return Template(react_system_prompt_template).substitute(
        tool_list=tool_list,
        workspace=workspace,
    )


def main():
    if not os.path.isdir(WORKSPACE):
        print(f"工作区目录不存在：{WORKSPACE}", file=sys.stderr)
        sys.exit(1)

    agent = ReActAgent(
        tools=TOOLS,
        system_prompt=build_system_prompt(TOOLS, WORKSPACE),
    )

    print(f"工作区：{WORKSPACE}")

    while True:
        task = input("\n请输入任务：")
        if not task.strip():
            break
        final_answer = agent.run(task)
        print(f"\n\n[任务结束] {final_answer}")


if __name__ == "__main__":
    main()

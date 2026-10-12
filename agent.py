"""ReAct Agent 主循环。

同步单线程执行：请求模型（流式打印）→ 流结束后解析标签 → 执行工具 → 回填观察 → 下一轮。
"""
import ast
import re
from typing import Callable, List, Tuple

from openai import OpenAI

from config import API_KEY, BASE_URL, MODEL

# 上下文护栏：对话历史超过这个条数就丢弃最早的记录（system 消息始终保留）。
# 64k 窗口按每条约 150~200 tokens 估算约有 300~400 条容量，这里保守取 200，
# 给"单条 observation 特别长"（如读到整个文件）的情况留出余量。
MAX_MESSAGES = 200


class ReActAgent:
    def __init__(self, tools: List[Callable], system_prompt: str):
        self.tools = {func.__name__: func for func in tools}
        self.client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
        self.model = MODEL
        # 对话历史跨任务保留：在这里建立，run() 只往里追加
        self.messages = [{"role": "system", "content": system_prompt}]

    def run(self, user_input: str) -> str:
        """执行 ReAct 循环，直到模型给出 <final_answer> 或用户中止。"""
        self.messages.append({"role": "user", "content": f"<question>{user_input}</question>"})

        while True:
            # 超过护栏就丢弃最早的记录（保留 system 消息）
            overflow = len(self.messages) - MAX_MESSAGES
            if overflow > 0:
                del self.messages[1:1 + overflow]

            # 请求模型：流式打印，返回一份格式合法的完整回复
            content = self.call_model(self.messages)

            # 有最终答案就结束
            final_match = re.search(r"<final_answer>(.*?)</final_answer>", content, re.DOTALL)
            if final_match:
                return final_match.group(1)

            # 否则必定是一个工具调用（格式合法性已由 call_model 保证）
            action_match = re.search(r"<action>(.*?)</action>", content, re.DOTALL)
            tool_name, args = self.parse_action(action_match.group(1))

            # 只有终端命令才需要用户确认，其余工具直接执行
            if tool_name == "run_terminal_command":
                should_continue = input("\n\n是否继续？（Y/N）")
                if should_continue.lower() != "y":
                    print("\n\n操作已取消。")
                    # 补一条 observation，避免历史里留下"有 action 没有结果"的悬空记录
                    self.messages.append({
                        "role": "user",
                        "content": "<observation>用户拒绝执行该命令，任务已中止。</observation>",
                    })
                    return "操作被用户取消"

            try:
                observation = self.tools[tool_name](*args)
            except Exception as e:
                observation = f"工具执行错误：{str(e)}"
            print(f"\n\n[Observation] {observation}")

            self.messages.append({
                "role": "user",
                "content": f"<observation>{observation}</observation>",
            })

    def call_model(self, messages) -> str:
        """同步流式请求：逐块打印并累积，直到拿到一份格式合法的回复。

        合法 = 含一对完整的 <final_answer> 或 <action> 标签。
        不合法就丢弃（不写进 messages）并重新请求，避免脏数据污染对话历史。
        """
        while True:
            print("\n\n正在请求模型，请稍等...")
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=True,
            )

            content = ""
            for chunk in stream:
                # 部分块（如末尾的用量统计）不带 choices，跳过
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta.content or ""
                if delta:
                    print(delta, end="", flush=True)
                    content += delta
            print()

            if self._reply_is_valid(content):
                messages.append({"role": "assistant", "content": content})
                return content

            print("[警告] 本次回复里没有完整的 <action> 或 <final_answer> 标签，已丢弃并重新请求")
            # 补一句提示再问：不合法的回复不入库，因此历史里会连着出现两条 user 消息
            messages.append({
                "role": "user",
                "content": "你刚才的回复没有按格式输出。请重新回答，务必包含完整的 <thought> 标签，"
                           "以及 <action> 或 <final_answer> 其中之一。",
            })

    @staticmethod
    def _reply_is_valid(content: str) -> bool:
        """回复是否合法：含一对完整的 <final_answer>，或一个可解析的 <action>。

        action 的内容必须是 "工具名(参数...)" 形式——标签里可能带多余空格，
        但若是整段自然语言，解析不出来，就当作不合法让它重答。
        """
        if re.search(r"<final_answer>(.*?)</final_answer>", content, re.DOTALL):
            return True

        action_match = re.search(r"<action>(.*?)</action>", content, re.DOTALL)
        if not action_match:
            return False
        return bool(re.match(r"\w+\s*\(", action_match.group(1).strip(), re.DOTALL))

    def parse_action(self, code_str: str) -> Tuple[str, List]:
        """解析 "工具名(参数, ...)" 形式的调用字符串，返回 (工具名, 参数列表)。

        模型输出的参数是源码文本而非 JSON：先按顶层逗号切开，再逐段转换。
        """
        match = re.match(r"(\w+)\s*\((.*)\)", code_str.strip(), re.DOTALL)
        if not match:
            raise ValueError("Invalid function call syntax")

        func_name, args_str = match.group(1), match.group(2).strip()
        args = [self._parse_single_arg(part) for part in self._split_args(args_str)]
        return func_name, args

    @staticmethod
    def _split_args(args_str: str) -> List[str]:
        """按顶层逗号把参数文本切开，返回每段的原始文本（保留引号）。

        引号内的逗号、括号内的逗号都不算分隔符。
        """
        parts = []
        current = ""
        quote = None  # 非 None 表示正处在该引号包围的字符串里
        depth = 0     # 括号嵌套深度

        for i, ch in enumerate(args_str):
            if quote is None and ch in ('"', "'"):
                quote = ch
            elif quote is not None:
                # 未被反斜杠转义的引号才结束字符串
                if ch == quote and args_str[i - 1] != "\\":
                    quote = None
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            elif ch == "," and depth == 0:
                parts.append(current.strip())
                current = ""
                continue

            current += ch

        if current.strip():
            parts.append(current.strip())
        return parts

    @staticmethod
    def _parse_single_arg(arg_str: str):
        """把单段参数文本转成 Python 值。

        字符串字面量只去外层引号，并还原引号转义与双反斜杠；
        不处理 \\n / \\t / \\r —— Windows 路径与终端命令里它们是正常字符，
        多行内容的 \\n 还原由 write_to_file 自己负责。
        其余类型交给 ast.literal_eval；解析失败则原样返回字符串。
        """
        arg_str = arg_str.strip()

        if len(arg_str) >= 2 and arg_str[0] == arg_str[-1] and arg_str[0] in ('"', "'"):
            inner = arg_str[1:-1].replace('\\"', '"').replace("\\'", "'")
            return inner.replace("\\\\", "\\")

        try:
            return ast.literal_eval(arg_str)
        except (SyntaxError, ValueError):
            return arg_str

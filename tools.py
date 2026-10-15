"""Agent 可调用的三个工具。

注意：本模块中每个函数的 docstring 会被注入系统提示词（模型据此决定怎么调用），
所以 docstring 必须写清用途、参数含义，并给出简单调用示例。
"""
import ctypes
import subprocess

# 单条命令的输出上限：超过就截断，避免一次请求撑爆上下文
MAX_OUTPUT_CHARS = 2000


def read_file(file_path):
    """读取文件内容。file_path 为工作区内的绝对路径，例：read_file("C:\\work\\a.txt")"""
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


def write_to_file(file_path, content):
    """写入文件。file_path 为工作区内的绝对路径，多行内容用 \\n 表示，例：write_to_file("C:\\work\\a.txt", "第一行\\n第二行")"""
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content.replace("\\n", "\n"))
    return "写入成功"


def run_terminal_command(command):
    """执行终端命令，返回命令的输出内容或错误信息，例：run_terminal_command("dir")"""
    # cmd.exe 的输出编码跟随控制台输出代码页，不是固定的某一种：
    #   - 代码页 936   → 输出 GBK（dir 表头是中文「驱动器 C 中的卷没有标签」）
    #   - 代码页 65001 → 输出 UTF-8（dir 表头会退回英文「Volume in drive C」）
    # 写死任何一种都会在另一种环境下把中文解成乱码（实测踩过：在 65001 的终端里，
    # 路径被解成 "ai鍥剧墖瑙嗛…"）。所以直接问 Windows 当前代码页，按它解码。
    # 没有控制台时（输出被重定向）回退到系统 OEM 代码页 —— cmd 此时用的就是它。
    # errors="replace" 保证遇到非预期字节时只降级显示，不抛异常。
    cp = ctypes.windll.kernel32.GetConsoleOutputCP() or ctypes.windll.kernel32.GetOEMCP()
    run_result = subprocess.run(
        command, shell=True, capture_output=True, text=True,
        encoding="cp%d" % cp, errors="replace"
    )

    if run_result.returncode != 0:
        # 失败信息有的命令写 stderr，有的写 stdout，取有内容的那个
        detail = run_result.stderr.strip() or run_result.stdout.strip()
        return f"命令执行失败（退出码 {run_result.returncode}）：{detail}"

    output = run_result.stdout.strip()
    if not output:
        return "执行成功（该命令没有输出）"
    if len(output) > MAX_OUTPUT_CHARS:
        return output[:MAX_OUTPUT_CHARS] + f"\n...（输出过长已截断，共 {len(output)} 字符）"
    return output

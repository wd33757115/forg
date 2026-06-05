"""CLI argument parser for Forge (extracted from main.py)."""

from __future__ import annotations

import argparse
import os
import textwrap

from forge.cli.scenarios import DEMO_SCENARIOS, SCENARIO_QUESTIONS, TYPE_ALIASES

CLI_EPILOG = """
示例:
  py main.py "等保三级登录401故障，请诊断"
  py main.py --type security --report --no-feedback
  py main.py --load .forge_state/cli-demo.json "继续优化方案"
  py main.py --web
"""


def build_cli_parser() -> argparse.ArgumentParser:
    """Build and return the Forge CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Forge — 项目级 AI 操作系统命令行工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(CLI_EPILOG),
    )
    parser.add_argument("question", nargs="?", help="问题描述（直接输入即运行完整流程）")
    parser.add_argument("-i", "--interactive", action="store_true", help="交互式选择场景/问题")
    parser.add_argument(
        "--example",
        type=int,
        choices=list(range(1, len(SCENARIO_QUESTIONS) + 1)),
        help="预设示例编号",
    )
    parser.add_argument(
        "--type",
        choices=list(TYPE_ALIASES.keys()),
        help="问题类型: security=等保 | itil=ITIL | general=通用 | mixed=混合",
    )
    parser.add_argument(
        "--scenario",
        choices=list(DEMO_SCENARIOS.keys()),
        help="预设场景（security | itil | mixed | general）",
    )
    parser.add_argument("--save", nargs="?", const="auto", metavar="PATH", help="保存状态+结果（简写）")
    parser.add_argument("--load", nargs="?", const="auto", metavar="PATH", help="加载状态继续运行（简写）")
    parser.add_argument(
        "--check-mode",
        choices=["strict", "advisory", "lenient"],
        default=None,
        help="合规检查严格度（默认 advisory）",
    )
    parser.add_argument(
        "--report",
        nargs="?",
        const="auto",
        metavar="PATH",
        help="导出 Markdown 运行报告",
    )
    parser.add_argument("--no-feedback", action="store_true", help="跳过满意度评分")
    parser.add_argument(
        "--demo-seed",
        action="store_true",
        help="为空白项目预置演示用文档/WBS（提升合规 partial 与资料生成稳定性）",
    )
    parser.add_argument(
        "--no-demo-seed",
        action="store_true",
        help="禁用演示证据预置（覆盖 --type/--scenario 的默认预置）",
    )
    parser.add_argument("--project-id", default="cli-demo", help="项目 ID")
    parser.add_argument("--protection-level", default="3", choices=["1", "2", "3", "4", "5"])
    parser.add_argument("-v", "--verbose", action="store_true", help="DEBUG 日志")
    parser.add_argument("--show-docs", action="store_true", help="打印完整 Markdown 资料")
    parser.add_argument("--log-file", help="日志输出文件")
    parser.add_argument(
        "--save-state",
        nargs="?",
        const="auto",
        metavar="PATH",
        help="运行后保存状态",
    )
    parser.add_argument("--load-state", metavar="PATH", help="加载状态；配合 --inspect 仅查看")
    parser.add_argument(
        "--resume",
        nargs="?",
        const="auto",
        metavar="PATH",
        help="从已保存状态恢复并运行新问题",
    )
    parser.add_argument("--inspect", action="store_true", help="仅查看 --load-state 内容")
    parser.add_argument("--list-states", action="store_true", help="列出 .forge_state/ 下已保存状态")
    parser.add_argument(
        "--save-result",
        nargs="?",
        const="auto",
        metavar="PATH",
        help="保存完整运行结果 JSON",
    )
    parser.add_argument("--web", action="store_true", help="启动 FastAPI Web 服务")
    parser.add_argument(
        "--host",
        default=os.environ.get("FORGE_WEB_HOST", "127.0.0.1"),
        help="Web 监听地址",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("FORGE_WEB_PORT", "8000")),
        help="Web 端口",
    )
    return parser

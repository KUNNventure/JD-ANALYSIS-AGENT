"""端到端入口 —— 支持 interrupt（human-in-the-loop）。

用法：
  python main.py
  python main.py --images test_images/jd1.png,test_images/jd2.png
  python main.py --request "只帮我做匹配"
  python main.py history          # 列表
  python main.py history 1        # 查看第 1 条详情（不用抄 uuid）
  python main.py history 1 --raw  # 第 1 条完整 JSON
"""

import argparse
import json
import uuid
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from langgraph.types import Command

DEFAULT_IMAGES = ["test_images/jd1.png", "test_images/jd2.png"]
DEFAULT_REQUEST = "帮我分析这份JD和简历的匹配度，给出求职准备建议和模拟面试包"

_OUTPUT_BY_STEP = {
    "T1": ("结构化 JD (T1)", "jd_structured"),
    "T2": ("匹配分析 (T2)", "match_result"),
    "T3": ("求职建议 (T3)", "suggestions"),
    "T4": ("模拟面试包 (T4)", "interview_pack"),
}


def _print_block(title: str, data, *, skip_if_empty=True):
    if skip_if_empty and not data:
        return
    print(f"\n{'=' * 8} {title} {'=' * 8}")
    if isinstance(data, (dict, list)):
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(data)


def _print_final_results(final: dict):
    plan = final.get("plan") or []
    retry = final.get("retry_count", 0)
    if retry:
        print(f"\n重试次数: {retry}")
    for step in plan:
        if step not in _OUTPUT_BY_STEP:
            continue
        title, state_key = _OUTPUT_BY_STEP[step]
        _print_block(title, final.get(state_key))


def _print_paths(label: str, paths: list):
    print(f"   {label}:")
    if not paths:
        print("     （无）")
        return
    for p in paths:
        exists = Path(p).exists()
        mark = "" if exists else " [文件不存在]"
        print(f"     · {p}{mark}")


def _log_node_event(node_name: str, node_output) -> None:
    """打印节点产出字段；executor/checker 已在节点内打日志，且 checker 空返回时 output 可能为 None。"""
    if node_output is None:
        return
    if node_name in ("executor", "checker"):
        return
    if isinstance(node_output, dict):
        print(f"[{node_name}] 产出字段: {list(node_output.keys())}")


def _print_interrupt(info: dict):
    """按 interrupt 类型展示提示（含 T1 缺失字段清单）。"""
    print(f"\n🔔 {info.get('message', '')}")
    itype = info.get("type", "low_score")

    if itype == "t1_missing_fields":
        labels = info.get("missing_labels") or info.get("missing_fields") or []
        if labels:
            print("   未能从截图提取到：")
            for label in labels:
                print(f"     · {label}")
        _print_paths("当前使用的截图", info.get("image_paths") or [])
        return

    if itype == "low_score":
        if "personal_score" in info:
            print(f"   个人维度: {info['personal_score']}")
            print(f"   岗位维度: {info['job_score']}")
            print(f"   加权总分: {info['weighted_total']}")
        if info.get("top_gaps"):
            print(f"   主要差距: {', '.join(info['top_gaps'])}")


def _resolve_image_paths(raw: str) -> list[str] | None:
    paths = [p.strip() for p in raw.split(",") if p.strip()]
    if not paths:
        return None
    missing = [p for p in paths if not Path(p).exists()]
    if missing:
        print(f"⚠️ 以下路径不存在: {', '.join(missing)}")
        return None
    return paths


def _prompt_resume_command(info: dict) -> Command:
    itype = info.get("type", "low_score")

    if itype == "t1_missing_fields":
        _print_paths("当前截图", info.get("image_paths") or [])
        print(
            "\n请输入补充后的 JD 截图路径（多张用英文逗号分隔）。\n"
            "直接回车 = 用当前路径再试一次；输入 n = 结束分析。"
        )
        raw = input("路径: ").strip()
        if raw.lower() in ("n", "no", "否", "不", "终止"):
            return Command(resume="n")
        if not raw:
            return Command(
                resume="y",
                update={"last_tool_error": "", "jd_structured": {}},
            )
        paths = _resolve_image_paths(raw)
        while paths is None:
            raw = input("请重新输入路径（或 n 结束）: ").strip()
            if raw.lower() in ("n", "no", "否", "不", "终止"):
                return Command(resume="n")
            if not raw:
                return Command(
                    resume="y",
                    update={"last_tool_error": "", "jd_structured": {}},
                )
            paths = _resolve_image_paths(raw)
        return Command(
            resume="y",
            update={
                "image_paths": paths,
                "jd_structured": {},
                "last_tool_error": "",
            },
        )

    answer = input("\n请输入 y(继续) 或 n(放弃): ").strip()
    return Command(resume=answer)


def _parse_images_arg(raw: str | None) -> list[str]:
    if not raw:
        return list(DEFAULT_IMAGES)
    paths = [p.strip() for p in raw.split(",") if p.strip()]
    missing = [p for p in paths if not Path(p).exists()]
    if missing:
        raise SystemExit(f"截图不存在: {', '.join(missing)}")
    return paths


def _build_initial_state(*, images: list[str], user_request: str) -> dict:
    from memory.resume_store import load_resume, seed_from_file_if_empty

    seeded_from = seed_from_file_if_empty(Path("resume.md"), Path("resume.template.md"))
    if seeded_from == "resume.template.md":
        print(
            "⚠️ 已从 resume.template.md 导入占位简历，请复制为 resume.md 并填写真实内容后再正式投递分析。\n"
        )
    resume = load_resume()
    return {
        "user_request": user_request,
        "image_paths": images,
        "plan": [],
        "current_step": 0,
        "jd_structured": {},
        "resume": resume["content"],
        "resume_fingerprint": resume["fingerprint"],
        "match_result": {},
        "suggestions": {},
        "interview_pack": {},
        "similar_jds": [],
        "retry_count": 0,
        "replan_count": 0,
        "needs_user_input": False,
        "last_tool_error": "",
    }


def run(*, images: list[str], user_request: str):
    from agent.graph import build_graph

    app = build_graph()
    thread_id = f"run-{uuid.uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": thread_id}}
    state = _build_initial_state(images=images, user_request=user_request)

    print("=== 开始执行 ===")
    print(f"thread_id: {thread_id}")
    _print_paths("JD 截图", images)
    print()

    last_interrupt: dict = {}

    for event in app.stream(state, config):
        for node_name, node_output in event.items():
            if node_name == "__interrupt__":
                last_interrupt = node_output[0].value
                _print_interrupt(last_interrupt)
            else:
                _log_node_event(node_name, node_output)

    snapshot = app.get_state(config)
    while snapshot.next:
        cmd = _prompt_resume_command(last_interrupt or {"type": "low_score"})

        for event in app.stream(cmd, config):
            for node_name, node_output in event.items():
                if node_name == "__interrupt__":
                    last_interrupt = node_output[0].value
                    _print_interrupt(last_interrupt)
                else:
                    _log_node_event(node_name, node_output)

        snapshot = app.get_state(config)

    print("\n=== 执行结束 ===")
    _print_final_results(snapshot.values)


def _cmd_history(args):
    from memory.history import print_history

    print_history(
        limit=args.limit,
        detail_jd_id=args.id,
        index=args.index,
        raw=args.raw,
    )


def main():
    parser = argparse.ArgumentParser(description="JD 分析 Agent")
    parser.add_argument(
        "--images",
        default=None,
        help="JD 截图路径，多张用英文逗号分隔（默认 test_images/jd1.png,jd2.png）",
    )
    parser.add_argument(
        "--request",
        default=DEFAULT_REQUEST,
        help="用户请求（传给 Planner）",
    )
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("run", help="分析 JD（默认命令，可省略）")
    h = sub.add_parser("history", help="查看历史 JD 分析")
    h.add_argument(
        "index",
        nargs="?",
        type=int,
        help="列表序号（与 history 列表左侧数字一致，1=最近一条）",
    )
    h.add_argument("--id", default=None, help="按 jd_id 或前缀查详情（可选，一般用序号即可）")
    h.add_argument("--limit", type=int, default=20, help="列表条数")
    h.add_argument("--raw", action="store_true", help="详情输出完整 JSON")

    args = parser.parse_args()
    if args.command == "history":
        _cmd_history(args)
        return

    images = _parse_images_arg(args.images)
    run(images=images, user_request=args.request)


if __name__ == "__main__":
    main()

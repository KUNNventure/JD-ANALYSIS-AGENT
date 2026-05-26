"""端到端入口 —— 支持 interrupt（human-in-the-loop）。

用法：
  python main.py              # 正常跑
  interrupt 触发时会暂停，提示你输入 y/n，然后恢复图继续执行。
"""

import json
from dotenv import load_dotenv
load_dotenv()

from pathlib import Path
from langgraph.types import Command
from agent.graph import build_graph
from memory.resume_store import load_resume, seed_from_file_if_empty

app = build_graph()

# 简历从 SQLite 读取；库为空时尝试从 resume.md 导入一次
seed_from_file_if_empty(Path("resume.md"))
_resume = load_resume()

# ========== 初始 state ==========
initial_state = {
    "user_request": "帮我分析这份JD和我的简历的匹配度，并给出求职准备建议和模拟面试包，不需要面试题",
    "image_paths": ["test_images/jd1.png", "test_images/jd2.png"],
    "plan": [],
    "current_step": 0,
    "jd_structured": {},
    "resume": _resume["content"],
    "resume_fingerprint": _resume["fingerprint"],
    "match_result": {},
    "suggestions": {},
    "interview_pack": {},
    "similar_jds": [],
    "retry_count": 0,
    "replan_count": 0,
    "needs_user_input": False,
    "last_tool_error": "",
}

# interrupt 必须有 thread_id
config = {"configurable": {"thread_id": "run-1"}}

# Planner 规划的 T* → state 字段与打印标题（与 nodes.executor 映射一致）
_OUTPUT_BY_STEP = {
    "T1": ("结构化 JD (T1)", "jd_structured"),
    "T2": ("匹配分析 (T2)", "match_result"),
    "T3": ("求职建议 (T3)", "suggestions"),
    "T4": ("模拟面试包 (T4)", "interview_pack"),
}


def _print_block(title: str, data, *, skip_if_empty=True):
    """打印一块 state 产物；空 dict/list 默认跳过（如 plan 未含 T4）。"""
    if skip_if_empty and not data:
        return
    print(f"\n{'=' * 8} {title} {'=' * 8}")
    # dict/list 格式化为 JSON，中文不转义；其余类型直接 str
    if isinstance(data, (dict, list)):
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(data)


def _print_final_results(final: dict):
    """按本次 plan 里规划的步骤，只打印已有产物的 state 字段。"""
    plan = final.get("plan") or []

    retry = final.get("retry_count", 0)
    if retry:
        print(f"\n重试次数: {retry}")

    for step in plan:
        if step not in _OUTPUT_BY_STEP:
            continue
        title, state_key = _OUTPUT_BY_STEP[step]
        _print_block(title, final.get(state_key))


def run():
    print("=== 开始执行 ===\n")

    # 第一轮：正常跑，遇到 interrupt 会自动停下来
    for event in app.stream(initial_state, config):
        for node_name, node_output in event.items():
            if node_name == "__interrupt__":
                # interrupt 触发了，打印提示信息
                info = node_output[0].value   # interrupt() 传出的那个 dict
                print(f"\n🔔 {info['message']}")
                print(f"   个人维度: {info['personal_score']}")
                print(f"   岗位维度: {info['job_score']}")
                print(f"   加权总分: {info['weighted_total']}")
                if info.get("top_gaps"):
                    print(f"   主要差距: {', '.join(info['top_gaps'])}")
            else:
                # 流式阶段只打字段名，完整内容在结束时由 _print_final_results 输出
                print(f"[{node_name}] 产出字段: {list(node_output.keys())}")

    # 检查是否有未处理的 interrupt
    snapshot = app.get_state(config)
    while snapshot.next:  # next 非空说明图还没结束（被 interrupt 暂停了）
        answer = input("\n请输入 y(继续) 或 n(放弃): ").strip()

        # 用 Command(resume=answer) 恢复图
        for event in app.stream(Command(resume=answer), config):
            for node_name, node_output in event.items():
                if node_name == "__interrupt__":
                    info = node_output[0].value
                    print(f"\n🔔 {info['message']}")
                else:
                    print(f"[{node_name}] 产出字段: {list(node_output.keys())}")

        snapshot = app.get_state(config)

    print("\n=== 执行结束 ===")
    # snapshot.values 即当前 thread 的完整 AgentState
    _print_final_results(snapshot.values)


if __name__ == "__main__":
    run()

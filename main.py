"""端到端入口 —— 支持 interrupt（human-in-the-loop）。

用法：
  python main.py              # 正常跑
  interrupt 触发时会暂停，提示你输入 y/n，然后恢复图继续执行。
"""

from dotenv import load_dotenv
load_dotenv()

from pathlib import Path
from langgraph.types import Command
from graph import build_graph

app = build_graph()

# ========== 初始 state ==========
initial_state = {
    "user_request": "帮我分析这份JD和我的简历的匹配度",
    "image_paths": ["test_images/jd1.png", "test_images/jd2.png"],
    "plan": [],
    "current_step": 0,
    "jd_structured": {},
    "resume": Path("resume.md").read_text(encoding="utf-8"),
    "match_result": {},
    "suggestions": {},
    "interview_pack": {},
    "retry_count": 0,
    "needs_user_input": False,
    "last_tool_error": "",      # 新增字段
}

# interrupt 必须有 thread_id
config = {"configurable": {"thread_id": "run-1"}}


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

    # 打印最终 state 关键字段
    final = snapshot.values
    print(f"\n匹配总分: {final.get('match_result', {}).get('weighted_total', 'N/A')}")
    print(f"重试次数: {final.get('retry_count', 0)}")
    if final.get("suggestions"):
        print("✅ 求职建议已生成")
    if final.get("interview_pack"):
        print("✅ 模拟面试包已生成")


if __name__ == "__main__":
    run()
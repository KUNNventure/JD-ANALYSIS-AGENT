"""端到端真跑入口。T1→T2→T3→T4 全部走真实实现。"""

from dotenv import load_dotenv
load_dotenv()

import json
from pathlib import Path
from graph import build_graph

app = build_graph()

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
}

print("=== 端到端真跑 ===\n")
final_state = None
for event in app.stream(initial_state):
    for node_name, node_output in event.items():
        print(f"[{node_name}] 产出字段: {list(node_output.keys())}")
        final_state = {**(final_state or initial_state), **node_output}

# 打印各工具产出
print("\n" + "=" * 50)
print("T1 - JD结构化:")
print(json.dumps(final_state.get("jd_structured", {}), ensure_ascii=False, indent=2))

print("\n" + "=" * 50)
print("T2 - 匹配结果:")
print(json.dumps(final_state.get("match_result", {}), ensure_ascii=False, indent=2))

print("\n" + "=" * 50)
print("T3 - 求职建议:")
print(json.dumps(final_state.get("suggestions", {}), ensure_ascii=False, indent=2))

print("\n" + "=" * 50)
print("T4 - 面试包:")
print(json.dumps(final_state.get("interview_pack", {}), ensure_ascii=False, indent=2))

print("\n=== 端到端完成 ===")
"""空跑入口。喂一句假请求，跑完整流程，打印 state 变化。"""

from dotenv import load_dotenv
load_dotenv()

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

print("=== 开始空跑 ===")
for event in app.stream(initial_state):
    for node_name, node_output in event.items():
        print(f"[{node_name}] 产出字段: {list(node_output.keys())}")
print("=== 空跑结束 ===")
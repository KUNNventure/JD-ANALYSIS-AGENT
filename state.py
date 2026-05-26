from typing import TypedDict

class AgentState(TypedDict):
    user_request: str       # 用户原始请求
    image_paths: list       # 用户输入的JD截图路径列表
    plan: list              # Planner 生成的工具调用计划 ["T1","T2","T3","T4"]
    current_step: int       # 执行进度（已完成到第几步）
    jd_structured: dict     # T1 产出：结构化 JD
    resume: dict            # 简历（贯穿全程的长期 state）
    match_result: dict      # T2 产出：三维匹配 + gap（含 below_threshold 字段）
    suggestions: dict       # T3 产出：招呼语 + 简历建议 + 交流建议
    interview_pack: dict    # T4 产出：模拟题 + 答案 + 准备建议
    retry_count: int        # 失败重规划计数（成功后归零）
    needs_user_input: bool  # human-in-the-loop：用户拒绝后为 True → 路由到 END
    last_tool_error: str    # 【新增】最近一次工具错误信息，空串=无错误
    
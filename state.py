from typing import TypedDict

class AgentState(TypedDict):
    user_request: str       # 用户原始请求
    image_paths: list      # 用户输入的JD截图路径列表
    plan: list              # Planner 生成的工具调用计划
    current_step: int       # 执行进度（已完成到第几步）
    jd_structured: dict     # T1 产出：结构化 JD
    resume: dict            # 简历（贯穿全程的长期 state）
    match_result: dict      # T2 产出：三维匹配 + gap
    suggestions: dict       # T3 产出：招呼语 + 简历建议 + 交流建议
    interview_pack: dict    # T4 产出：模拟题 + 答案 + 准备建议
    retry_count: int        # 失败重规划计数
    needs_user_input: bool  # human-in-the-loop 标志

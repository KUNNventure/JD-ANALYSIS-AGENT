from typing import TypedDict

class AgentState(TypedDict):
    user_request: str       # 用户原始请求
    image_paths: list       # 用户输入的JD截图路径列表
    plan: list              # Planner 生成的工具调用计划 ["T1","T2","T3","T4"]
    current_step: int       # 执行进度（已完成到第几步）
    jd_structured: dict     # T1 产出：结构化 JD（含 raw_text，仅当次 run）
    resume: str             # 当前简历全文（来源：resume 库最新版）
    resume_fingerprint: str # 简历版本指纹（写入 match_snapshot）
    match_result: dict      # T2 产出：三维匹配 + gap（含 below_threshold 字段）
    suggestions: dict       # T3 产出：招呼语 + 简历建议 + 交流建议
    interview_pack: dict    # T4 产出：模拟题 + 答案 + 准备建议
    retry_count: int        # 当前步骤失败重试次数（成功后归零；达上限走 degrade）
    replan_count: int       # Planner 重出 plan 次数（带错误重规划，上限 2）
    needs_user_input: bool  # human-in-the-loop：用户拒绝后为 True → 路由到 END
    last_tool_error: str    # 最近一次工具错误信息，空串=无错误
    similar_jds: list       # T2 检索到的相似历史 JD（含 match_snapshot）

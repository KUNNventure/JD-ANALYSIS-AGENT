"""Planner 和 Executor 两个核心节点。骨架阶段逻辑全部写死。"""

from tools.mock_tools import mock_t2, mock_t3, mock_t4
from tools.t1 import t1

# 工具名 → 工具函数 的映射，Executor 靠它找到该调哪个工具
TOOL_MAP = {
    "T1": t1,
    "T2": mock_t2,
    "T3": mock_t3,
    "T4": mock_t4,
}


def planner(state):
    """Planner 节点：生成工具调用计划。
    Day2 写死为固定顺序，Day9 再换成 LLM 真实规划。"""
    return {
        "plan": ["T1", "T2", "T3", "T4"],
        "current_step": 0,
    }


def executor(state):
    """Executor 节点：按 plan 执行当前这一步的工具。
    (节点函数返回的是dict不是改state,框架自动把他合并进State)
    每次只走一步，结果写回 state，current_step + 1。"""
    step = state["current_step"]
    tool_name = state["plan"][step]      # 取当前该执行的工具名
    tool_func = TOOL_MAP[tool_name]      # 找到对应的工具函数
    result = tool_func(state)            # 调用它，拿到（假）结果

    # 不同工具的产出写进 state 不同字段
    field_map = {
        "T1": "jd_structured",
        "T2": "match_result",
        "T3": "suggestions",
        "T4": "interview_pack",
    }
    return {
        field_map[tool_name]: result,
        "current_step": step + 1,
    }
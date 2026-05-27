"""组装 LangGraph StateGraph —— 三条分支版。

分支1：正常推进 — executor 成功 → checker 校验 → 继续下一步或 END
分支2：失败处理 — 同一步重试最多 MAX_RETRIES 次 → 仍失败则 degrade → Planner 带错误重出 plan（replan_count 上限 2）
分支3：human-in-the-loop — T2 低分 → interrupt 问用户 → 继续或 END
"""

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver   # interrupt 必须有 checkpointer
from agent.state import AgentState
from agent.nodes import planner, executor, degrade, human_check, checker

MAX_RETRIES = 3   # 同一工具、同一步：失败重试上限（不是重规划，不改 plan）


# ========== 路由函数 ==========

def route_after_executor(state):
    """executor 跑完后的路由：工具抛错走分支2；成功则进 checker 验产出。"""
    # plan 为空 = Planner 重规划次数用尽，终止
    if not state.get("plan"):
        return END

    # ---- 分支2：工具失败（先同一步重试，再交 Planner 重规划）----
    if state.get("last_tool_error"):
        if state["retry_count"] >= MAX_RETRIES:
            return "degrade"       # 重试耗尽 → 交 Planner 重出 plan
        return "executor"          # 未耗尽 → 同一步再执行一次

    # executor 无异常：进 checker 校验刚写完的 T1/T2 产出（T3/T4 不校验）
    return "checker"


def route_after_checker(state):
    """checker 跑完后的三岔路口（分支2/3/1 的后续）。"""
    # plan 为空 = checker 让用户终止，或 Planner 重规划次数用尽
    if not state.get("plan"):
        return END

    # ---- 分支2：checker 判定产出不合格（回退 current_step，重跑同一步工具）----
    if state.get("last_tool_error"):
        if state["retry_count"] >= MAX_RETRIES:
            return "degrade"       # 重试耗尽 → 交 Planner 重出 plan
        return "executor"          # 未耗尽 → 同一步再执行一次

    # ---- 分支3：T2 完成后检查匹配度 ----
    #   刚跑完的步骤 = plan[current_step - 1]，若是 T2 且低于阈值 → human_check
    #   （不再写死 current_step==2，避免 plan 裁剪后路由失效）
    prev = state["current_step"] - 1
    if prev >= 0 and state["plan"][prev] == "T2":
        if state.get("match_result", {}).get("below_threshold"):
            return "human_check"

    # ---- 分支1：正常推进 ----
    if state["current_step"] < len(state["plan"]):
        return "executor"
    return END


def route_after_human_check(state):
    """用户决定后：拒绝 → END，确认 → 继续执行 T3。"""
    if state.get("needs_user_input"):
        return END
    return "executor"


# ========== 构建图 ==========

def build_graph():
    graph = StateGraph(AgentState)

    # 五个节点
    graph.add_node("planner", planner)
    graph.add_node("executor", executor)
    graph.add_node("checker", checker)
    graph.add_node("degrade", degrade)
    graph.add_node("human_check", human_check)

    # 入口 + 固定边
    graph.set_entry_point("planner")
    graph.add_edge("planner", "executor")

    # 四组条件边（executor → checker → 分支路由；human_check / degrade 各一条）
    graph.add_conditional_edges("executor", route_after_executor)
    graph.add_conditional_edges("checker", route_after_checker)
    graph.add_conditional_edges("human_check", route_after_human_check)
    graph.add_edge("degrade", "planner")   # degrade 后必回 Planner（带 last_tool_error）

    # interrupt 必须有 checkpointer，用内存版（生产环境换 SQLite/Postgres）
    memory = MemorySaver()
    return graph.compile(checkpointer=memory)

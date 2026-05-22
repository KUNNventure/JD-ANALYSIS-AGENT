"""组装 LangGraph StateGraph。Day2 只搭'正常推进'一条分支。"""

from langgraph.graph import StateGraph, END
from state import AgentState
from nodes import planner, executor


def route_after_executor(state):
    """路由函数：Executor 跑完一步后决定下一步去哪。
    plan 还没走完 → 回 executor 继续；走完了 → 结束。"""
    if state["current_step"] < len(state["plan"]):
        return "executor"
    return END


def build_graph():
    """构建并编译 StateGraph。"""
    graph = StateGraph(AgentState)

    graph.add_node("planner", planner)
    graph.add_node("executor", executor)

    graph.set_entry_point("planner")        # 入口：先跑 planner
    graph.add_edge("planner", "executor")   # planner 跑完固定去 executor（固定边）

    # executor 跑完走条件路由：由 route_after_executor 决定下一站
    graph.add_conditional_edges("executor", route_after_executor)

    return graph.compile()
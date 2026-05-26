"""Planner / Executor / Degrade / HumanCheck 四个节点。

三条分支：
  1. 正常推进：executor 成功 → 路由回 executor 或 END
  2. 失败重规划：executor 异常 → retry_count++ → 路由回 executor 重试；超3次 → degrade 跳过
  3. human-in-the-loop：T2 below_threshold → human_check interrupt → 用户决定继续或放弃
"""

from langgraph.types import interrupt
from tools.tool_defs import t1, t2, t3, t4

# ========== 工具映射 ==========
TOOL_MAP = {
    "T1": t1,
    "T2": t2,
    "T3": t3,
    "T4": t4,
}


# ========== 节点 1：Planner ==========
def planner(state):
    """生成工具调用计划。当前写死顺序，后续可换 LLM 规划。"""
    return {
        "plan": ["T1", "T2", "T3", "T4"],
        "current_step": 0,
    }


# ========== 节点 2：Executor（核心改动）==========
def executor(state):
    """按 plan 执行当前步骤的工具。

    成功：结果写入对应 state 字段，current_step+1，清空错误，retry归零。
    失败：错误信息写入 last_tool_error，retry_count+1，current_step 不动（下次重试同一步）。
    """
    step = state["current_step"]
    tool_name = state["plan"][step]
    tool_func = TOOL_MAP[tool_name]

    # ---- 失败重规划的核心：try/except ----
    try:
        result = tool_func(state)
    except Exception as e:
        # 不推进 current_step → 路由会让它重试同一步
        print(f"❌ [{tool_name}] 执行失败: {e}")
        return {
            "last_tool_error": f"[{tool_name}] {str(e)}",
            "retry_count": state["retry_count"] + 1,
        }

    # ---- 成功路径 ----
    field_map = {
        "T1": "jd_structured",
        "T2": "match_result",
        "T3": "suggestions",
        "T4": "interview_pack",
    }
    return {
        field_map[tool_name]: result,
        "current_step": step + 1,
        "last_tool_error": "",   # 清空错误
        "retry_count": 0,        # 成功后归零
    }


# ========== 节点 3：Degrade（重试超限降级）==========

# 依赖关系：值里的工具依赖键的产出，键挂了 → 值全跑不了 → 直接终止
# T1 产出 jd_structured → T2/T3/T4 都要用 → T1 挂 = 全链路死
# T2 产出 match_result  → T3/T4 要用       → T2 挂 = 后面全死
# T3 产出 suggestions   → T4 不依赖 T3     → T3 挂 = 跳过，T4 照跑
# T4 是最后一个                              → T4 挂 = 跳过，结束
CRITICAL_TOOLS = {"T1", "T2"}  # 这些挂了后面没法跑，必须终止


def degrade(state):
    """重试超限的降级策略：关键工具 → 终止；非关键 → 跳过继续。"""
    step = state["current_step"]
    tool_name = state["plan"][step]

    if tool_name in CRITICAL_TOOLS:
        # 关键工具挂了，后面全依赖它的产出，继续没意义
        print(f"🛑 [{tool_name}] 重试 {state['retry_count']} 次仍失败，该工具产出是后续必需输入，终止流程")
        return {
            "current_step": len(state["plan"]),  # 直接跳到末尾 → 路由走 END
            "last_tool_error": f"[{tool_name}] 关键工具失败，流程终止",
            "retry_count": 0,
        }
    else:
        # 非关键工具，跳过继续
        print(f"⚠️ [{tool_name}] 重试 {state['retry_count']} 次仍失败，跳过")
        return {
            "current_step": step + 1,
            "last_tool_error": "",
            "retry_count": 0,
        }


# ========== 节点 4：HumanCheck（匹配度低于阈值）==========
def human_check(state):
    """T2 匹配度低于阈值时触发 interrupt，暂停等用户决定。

    interrupt() 会暂停整个图，把消息返回给调用方。
    调用方用 Command(resume="y") 或 Command(resume="n") 恢复。
    resume 的值就是 interrupt() 的返回值。
    """
    match = state["match_result"]
    scores = match["scores"]
    total = match["weighted_total"]

    # interrupt 暂停图，把这个 dict 返回给调用方展示
    answer = interrupt({
        "message": f"⚠️ 匹配度总分 {total}，低于阈值 60。是否继续准备这家？(y/n)",
        "personal_score": scores["personal"],
        "job_score": scores["job"],
        "weighted_total": total,
        "top_gaps": [g["missing"] for g in match.get("gaps", [])[:3]],
    })

    # 用户恢复后，answer 就是他传入的值
    if str(answer).strip().lower() in ("n", "no", "否", "不", "放弃", "skip"):
        print("🛑 用户放弃该岗位")
        return {"needs_user_input": True}   # True = 用户拒绝 → 路由到 END
    print("✅ 用户确认继续")
    return {"needs_user_input": False}       # 继续 T3/T4
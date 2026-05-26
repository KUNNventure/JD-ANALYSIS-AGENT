"""Planner / Executor / Degrade / HumanCheck 四个节点。

三条分支：
  1. 正常推进：executor 成功 → 路由回 executor 或 END
  2. 失败重规划：executor 异常 → retry_count++ → 路由回 executor 重试；超3次 → degrade 跳过
  3. human-in-the-loop：T2 below_threshold → human_check interrupt → 用户决定继续或放弃
"""

from langgraph.types import interrupt
from tools.tool_defs import t1, t2, t3, t4
import state
import json
import dashscope
from dashscope import Generation

STRONG_MODEL = "qwen-max"  # 强模型

# ========== 工具映射 ==========
TOOL_MAP = {
    "T1": t1,
    "T2": t2,
    "T3": t3,
    "T4": t4,
}


# ========== 节点 1：Planner ==========
TOOL_DESCRIPTIONS = """
可用工具列表：
- T1: JD解析入库。输入：JD截图。输出：结构化JD数据。前置条件：用户提供了JD截图。
- T2: 简历-JD匹配。输入：结构化JD + 简历。输出：三维匹配度 + gap清单 + 岗位/公司画像。前置条件：T1已完成。
- T3: 求职准备建议。输入：匹配结果 + JD原文。输出：招呼语 + 简历修改建议。前置条件：T2已完成。
- T4: 模拟面试包。输入：JD + gap清单。输出：模拟题 + 参考答案。前置条件：T2已完成。
"""

def planner(state):
    """调用强模型，根据用户请求动态生成工具调用计划。"""
    replan = state.get("replan_count", 0)
    if replan >= 2:
        print("🛑 已重规划2次仍失败，终止流程")
        return {
            "plan": [],
            "current_step": 0,
            "replan_count": replan,
        }

    user_request = state.get("user_request", "")
    last_error = state.get("last_tool_error", "")

    # 构造 prompt
    prompt = f"""你是一个求职辅助Agent的规划器。根据用户请求，决定需要调用哪些工具、以什么顺序执行。

{TOOL_DESCRIPTIONS}

规则：
1. 默认情况下（用户没有特别指定），必须规划完整流程 T1→T2→T3→T4，不能跳过任何一步
2. 注意依赖关系：T2/T3/T4 都依赖 T1 的产出；T3/T4 依赖 T2 的产出
3. T3 和 T4 互不依赖，可以都选或只选其一
4. 对于用户有明确要求的任务，比如"只匹配""不需要面试题"等，只输出需要的工具，不要多余的工具

用户请求：{user_request}
"""

    # 如果是重规划（带着上次失败信息来的），追加上下文
    if last_error:
        prompt += f"""
上一次执行中发生了错误：{last_error}
请根据错误信息调整计划。如果某个工具反复失败，可以跳过它（前提是后续工具不依赖它）。
已完成的步骤不要重复规划。当前已执行到 step {state.get('current_step', 0)}。
"""

    prompt += """
请只输出一个 JSON 数组，例如 ["T1","T2","T3","T4"] 或 ["T1","T2"]。
不要输出任何其他内容。"""

    resp = Generation.call(
        model=STRONG_MODEL,
        messages=[{"role": "user", "content": prompt}],
        result_format="message",
        temperature=0.3,
    )

    if resp.status_code != 200:
        # LLM 挂了就降级回写死的全流程
        print(f"⚠️ Planner LLM 调用失败，降级为固定计划: {resp.code} {resp.message}")
        return {"plan": ["T1", "T2", "T3", "T4"], "current_step": 0}

    text = resp.output.choices[0].message.content.strip()
    text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    try:
        plan = json.loads(text)
        # 校验：必须是合法工具名的列表
        valid = {"T1", "T2", "T3", "T4"}
        plan = [t for t in plan if t in valid]
        if not plan:
            raise ValueError("空计划")
    except (json.JSONDecodeError, ValueError) as e:
        print(f"⚠️ Planner 输出解析失败({e})，降级为固定计划")
        plan = ["T1", "T2", "T3", "T4"]

    print(f"📋 Planner 规划: {plan}")

    return {
        "plan": plan,
        "current_step": 0,
        "last_tool_error": "",
        "retry_count": 0,
        "replan_count": replan + (1 if last_error else 0),  # 关键：有错误才+1，首次规划不加
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

    # T1 特殊处理：新数据覆盖旧数据，旧数据补缺
    if tool_name == "T1" and state.get("jd_structured"):
        old = state["jd_structured"]
        merged = {**old, **{k: v for k, v in result.items() if v}}  # 新值非空才覆盖
        # 列表字段特殊处理：新的非空列表覆盖，空列表保留旧的
        for key in ["tech_stack", "requirements", "responsibilities", "bonus"]:
            if not result.get(key) and old.get(key):
                merged[key] = old[key]
        result = merged
        print(f"🔀 [T1] 已合并新旧数据")

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

def degrade(state):
    """重试超限：不再自己决定跳过/终止，而是回 Planner 带着错误信息重新规划。"""
    step = state["current_step"]
    tool_name = state["plan"][step]
    print(f"⚠️ [{tool_name}] 重试 {state['retry_count']} 次仍失败，交回 Planner 重规划")
    # 不改 current_step，不清 last_tool_error → Planner 能看到是哪个工具挂了
    return {
        "retry_count": 0,  # 重规划后重置计数
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

# ========== 节点 5：Checker（产出校验）==========

# 每个工具产出后，下一步需要哪些关键字段
REQUIRED_FIELDS = {
    "T1": {
        "state_key": "jd_structured",
        "must_have": ["job_title", "tech_stack", "requirements", "responsibilities"],
        "warn_if_empty": ["company", "location", "salary"],  # 缺了不致命但值得警告
    },
    "T2": {
        "state_key": "match_result",
        "must_have": ["scores", "gaps", "weighted_total"],
        "warn_if_empty": [],
    },
    # T3/T4 是末端输出，不做强校验
}

def checker(state):
    step = state["current_step"] - 1
    if step < 0:
        return {}
    
    tool_name = state["plan"][step]
    spec = REQUIRED_FIELDS.get(tool_name)
    if not spec:
        return {}
    
    output = state.get(spec["state_key"], {})
    if not output:
        return {
            "last_tool_error": f"[Checker] {tool_name} 产出为空",
            "retry_count": state["retry_count"] + 1,
            "current_step": step,
        }
    
    missing = [f for f in spec["must_have"] if not output.get(f)]
    
    if missing and tool_name == "T1":
        if state["retry_count"] == 0:
            # 第一次缺字段：重试一次（可能是模型抽取不稳定）
            print(f"⚠️ [Checker] T1 缺少字段 {missing}，重试一次")
            return {
                "last_tool_error": f"[Checker] T1 缺少关键字段: {missing}",
                "retry_count": 1,
                "current_step": step,
            }
        else:
            # 重试过了还缺：问用户
            answer = interrupt({
                "message": f"⚠️ JD截图中未能提取到以下关键信息: {missing}。"
                           f"请确认您上传的截图中是否包含这些内容？(y=未包含,请上传包含这些信息的截图,继续分析 / n=截图不包含这些信息,终止分析)",
                "missing_fields": missing,
            })
            if str(answer).strip().lower() in ("n", "no", "否", "不", "终止"):
                print(f"🛑 用户确认截图不包含这些关键信息，终止分析")
                return {
                    "plan": [],  # 清空 plan → 路由走 END
                    "last_tool_error": f"用户确认JD截图缺少 {missing} 信息，终止",
                }
            else:
                # 用户说有，让他重新上传再跑
                print(f"🔄 用户确认包含信息，等待重新上传新截图后继续跑 T1")
                return {
                    "last_tool_error": f"[Checker] 用户确认有信息，继续跑T1",
                    "retry_count": 0,
                    "current_step": step,
                }
    
    if missing:
        # 非 T1 的缺字段走通用重试
        return {
            "last_tool_error": f"[Checker] {tool_name} 缺少关键字段: {missing}",
            "retry_count": state["retry_count"] + 1,
            "current_step": step,
        }
    
    # 警告字段
    empty = [f for f in spec["warn_if_empty"] if not output.get(f)]
    if empty:
        print(f" [Checker] {tool_name} 以下字段为空: {empty}")
    
    print(f"✅ [Checker] {tool_name} 产出校验通过")
    return {}
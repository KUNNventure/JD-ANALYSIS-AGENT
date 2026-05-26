"""四个工具的节点定义（薄 wrapper 层）。
每个函数从 state 取所需字段 → 调核心实现 → 返回 dict。
executor 通过 TOOL_MAP 找到对应函数调用。
"""

from tools.jd_parser import parse_jd
from memory.jd_store import store_jd, update_after_t2, update_advice_archive, build_match_snapshot
from tools.jd_matcher import match_jd
from tools.job_advisor import generate_advice
from tools.interview_prep import generate_interview_pack


def t1(state: dict) -> dict:
    """T1 JD解析入库：截图 → 多模态LLM结构化 → 存Chroma → 返回结构化JD。"""
    image_paths = state["image_paths"]
    jd = parse_jd(image_paths)
    store_jd(jd)
    return jd.model_dump()


def t2(state: dict) -> dict:
    """T2 简历-JD匹配：结构化JD + 简历 → 强模型两维打分 → 加权/阈值 → 匹配结果。"""
    fp = state.get("resume_fingerprint", "")
    out = match_jd(state["jd_structured"], state["resume"])
    # T2 结束：match_snapshot 写回 Chroma 长期记忆
    jd_id = state["jd_structured"].get("jd_id")
    if jd_id:
        update_after_t2(jd_id, build_match_snapshot(out["match_result"], fp))
    return out


def t3(state: dict) -> dict:
    """T3 求职准备建议：JD + 匹配结果 + 简历 → 招呼语 + 简历修改建议 + 交流建议。"""
    result = generate_advice(
        state["jd_structured"],
        state["match_result"],
        state["resume"],
    )
    # T3 结束：建议归档（不参与检索）
    jd_id = state["jd_structured"].get("jd_id")
    if jd_id:
        update_advice_archive(jd_id, suggestions=result)
    return result


def t4(state: dict) -> dict:
    """T4 模拟面试包：JD + 匹配结果 → 模拟题 + 答案要点 + 准备建议。"""
    result = generate_interview_pack(
        state["jd_structured"],
        state["match_result"],
    )
    # T4 结束：面试包归档（不参与检索）
    jd_id = state["jd_structured"].get("jd_id")
    if jd_id:
        update_advice_archive(jd_id, interview_pack=result)
    return result

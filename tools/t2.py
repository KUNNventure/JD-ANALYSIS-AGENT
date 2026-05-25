"""T2 工具：简历-JD 匹配的真实实现，替换 mock_t2。

executor 会以 t2(state) 调用本函数，返回值写进 state["match_result"]。
"""
from tools.jd_matcher import match_jd


def t2(state: dict) -> dict:
    """T2 简历-JD 匹配节点。

    流程：取结构化 JD + 简历 → 强模型两维打分 → Python 加权/阈值 → 返回匹配结果。

    Args:
        state: AgentState，需含 jd_structured（T1 产出）和 resume（简历文本）字段
    Returns:
        dict: 匹配结果（executor 会写进 state["match_result"]）
    """
    return match_jd(state["jd_structured"], state["resume"])
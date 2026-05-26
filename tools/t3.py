"""T3 工具：求职准备建议的薄 wrapper。

executor 会以 t3(state) 调用，返回值写进 state["suggestions"]。
"""
from tools.job_advisor import generate_advice


def t3(state: dict) -> dict:
    """T3 求职准备建议节点。

    输入：jd_structured（T1）+ match_result（T2）+ resume
    输出：招呼语 + 简历修改建议 + 交流建议
    """
    return generate_advice(
        state["jd_structured"],
        state["match_result"],
        state["resume"],
    )
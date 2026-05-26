"""T4 工具：模拟面试包的薄 wrapper。

executor 会以 t4(state) 调用，返回值写进 state["interview_pack"]。
"""
from tools.interview_prep import generate_interview_pack


def t4(state: dict) -> dict:
    """T4 模拟面试包节点。

    输入：jd_structured（T1）+ match_result（T2）
    输出：模拟题 + 参考答案 + 面试准备建议
    """
    return generate_interview_pack(
        state["jd_structured"],
        state["match_result"],
    )
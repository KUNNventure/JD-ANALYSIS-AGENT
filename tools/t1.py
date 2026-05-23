"""T1 工具：JD解析入库的真实实现，替换 mock_t1。

executor 会以 t1(state) 调用本函数，返回值写进 state["jd_structured"]。
"""

from tools.jd_parser import parse_jd
from tools.jd_store import store_jd


def t1(state: dict) -> dict:
    """T1 JD解析入库节点。

    流程：读截图路径 → Qwen-VL解析 → 存进Chroma → 返回结构化JD。

    Args:
        state: AgentState，需含 image_paths 字段
    Returns:
        dict: 结构化JD（executor会写进 state["jd_structured"]）
    """
    image_paths = state["image_paths"]

    jd = parse_jd(image_paths)   # → JDStructured 对象
    store_jd(jd)                 # 整条存进本地Chroma（长期记忆）

    # state["jd_structured"] 类型是 dict，把Pydantic对象转成dict
    return jd.model_dump()
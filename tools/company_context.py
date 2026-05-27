"""把 JD 里的公司/工商信息格式化成 prompt 片段，供 T2/T3/T4 共用。"""

import json


def format_company_block(jd_structured: dict) -> str:
    """有 company_info 用工商数据；否则说明仅能从 JD 推断。"""
    info = jd_structured.get("company_info")
    company = jd_structured.get("company") or "未知"
    if info:
        return (
            f"公司名称：{company}\n"
            f"工商信息（来自截图）：\n{json.dumps(info, ensure_ascii=False, indent=2)}"
        )
    return (
        f"公司名称：{company}\n"
        "（未提供工商信息截图，请结合 JD 描述与公司名自行推断，结论标注为推断）"
    )

"""各工具完成后的一行摘要（给终端进度用）。"""


def summarize_tool(tool_name: str, payload) -> str:
    """tool 成功后的单行摘要；payload 为写入 state 的内容或 T2 的 result dict。"""
    if tool_name == "T1":
        jd = payload if isinstance(payload, dict) else {}
        title = jd.get("job_title") or "—"
        company = jd.get("company") or "—"
        n_stack = len(jd.get("tech_stack") or [])
        return f"岗位={title} | 公司={company} | 技术栈 {n_stack} 项"

    if tool_name == "T2":
        if isinstance(payload, dict) and "match_result" in payload:
            m = payload["match_result"]
        else:
            m = payload or {}
        total = m.get("weighted_total", "—")
        gaps = len(m.get("gaps") or [])
        similar = len(payload.get("similar_jds", [])) if isinstance(payload, dict) else 0
        extra = f" | 历史相似 {similar} 条" if similar else ""
        return f"加权总分={total} | gap {gaps} 条{extra}"

    if tool_name == "T3":
        s = payload or {}
        vi = (s.get("company_viability") or {}).get("verdict", "—")
        greet_len = len(s.get("greeting") or "")
        return f"公司结论={vi} | 招呼语 {greet_len} 字 | 简历建议 {len(s.get('resume_advice') or [])} 条"

    if tool_name == "T4":
        pack = payload or {}
        n_q = len(pack.get("questions") or [])
        return f"模拟题 {n_q} 道 | 准备建议 {len(pack.get('prep_advice') or [])} 条"

    return ""

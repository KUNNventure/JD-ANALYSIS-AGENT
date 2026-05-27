"""JD 分析历史查询（读 Chroma 里的 match_snapshot + advice_archive）。"""

import json

from memory.jd_store import get_jd_record, list_all_records


def _fmt_score(snap: dict) -> str:
    total = snap.get("weighted_total")
    return str(total) if total is not None else "—"


def _print_detail(rec: dict) -> None:
    snap = rec.get("match_snapshot") or {}
    arch = rec.get("advice_archive") or {}
    sug = arch.get("suggestions") or {}
    pack = arch.get("interview_pack") or {}

    print(f"\n{'=' * 10} JD 摘要 {'=' * 10}")
    print(f"jd_id: {rec.get('jd_id')}")
    print(f"岗位: {rec.get('job_title') or '—'} @ {rec.get('company') or '—'}")
    print(f"薪资: {rec.get('salary') or '—'}")
    if rec.get("company_info"):
        print(f"工商: {json.dumps(rec['company_info'], ensure_ascii=False)}")

    print(f"\n{'=' * 10} 匹配 (T2) {'=' * 10}")
    if snap:
        print(f"加权总分: {_fmt_score(snap)}")
        scores = snap.get("scores") or {}
        if scores:
            print(f"  个人 {scores.get('personal')} / 岗位 {scores.get('job')}")
        if snap.get("jd_decoded"):
            print(f"JD 黑话: {snap['jd_decoded'][:200]}…" if len(snap.get("jd_decoded", "")) > 200 else f"JD 黑话: {snap.get('jd_decoded')}")
        for g in snap.get("top_gaps") or []:
            print(f"  gap [{g.get('severity')}]: {g.get('missing')}")
    else:
        print("（无匹配快照，可能只跑了 T1）")

    print(f"\n{'=' * 10} 求职建议 (T3) {'=' * 10}")
    if sug:
        vi = sug.get("company_viability") or {}
        print(f"值不值得投: {vi.get('verdict', '—')}")
        for r in (vi.get("reasons") or [])[:3]:
            print(f"  · {r}")
        prof = sug.get("company_profile") or {}
        if prof.get("summary"):
            print(f"公司画像: {prof['summary'][:150]}…" if len(prof.get("summary", "")) > 150 else f"公司画像: {prof.get('summary')}")
        if sug.get("greeting"):
            print(f"招呼语: {sug['greeting'][:120]}…" if len(sug["greeting"]) > 120 else f"招呼语: {sug['greeting']}")
    else:
        print("（未生成）")

    print(f"\n{'=' * 10} 面试包 (T4) {'=' * 10}")
    if pack:
        qs = pack.get("questions") or []
        print(f"共 {len(qs)} 道题")
        for i, q in enumerate(qs[:3], 1):
            print(f"  {i}. [{q.get('category')}] {q.get('question', '')[:80]}")
        if len(qs) > 3:
            print(f"  … 另有 {len(qs) - 3} 道，可用 --id 看完整 JSON")
    else:
        print("（未生成）")

    prefix = (rec.get("jd_id") or "")[:8]
    print(f"\n完整 JSON: python main.py history --id {prefix} --raw")


def _resolve_by_index(records: list[dict], index: int, *, limit: int) -> dict | None:
    """按列表序号取记录（1=最近一条，与列表打印的序号一致）。"""
    shown = records[:limit]
    if index < 1 or index > len(shown):
        print(f"序号 {index} 无效，当前列表为 1–{len(shown)}（先运行 python main.py history 看列表）")
        return None
    return shown[index - 1]


def _resolve_by_id(jd_id: str) -> dict | None:
    """精确 jd_id；否则按前缀匹配（列表里 [971b6b61…] 可只输入前缀）。"""
    rec = get_jd_record(jd_id)
    if rec:
        return rec
    records = list_all_records()
    matches = [r for r in records if r.get("jd_id", "").startswith(jd_id)]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        print(f"前缀「{jd_id}」匹配到 {len(matches)} 条，请用序号查看，例如：")
        for i, r in enumerate(matches[:8], 1):
            print(f"  python main.py history {i}  # {r.get('company')} · {r.get('job_title')}")
        return None
    print(f"未找到 jd_id={jd_id}")
    return None


def _show_record(rec: dict, *, raw: bool) -> None:
    if raw:
        print(json.dumps(rec, ensure_ascii=False, indent=2))
    else:
        _print_detail(rec)


def print_history(
    *,
    limit: int = 20,
    detail_jd_id: str | None = None,
    index: int | None = None,
    raw: bool = False,
) -> None:
    records = list_all_records()

    if index is not None:
        rec = _resolve_by_index(records, index, limit=limit)
        if rec:
            _show_record(rec, raw=raw)
        return

    if detail_jd_id:
        rec = _resolve_by_id(detail_jd_id)
        if rec:
            _show_record(rec, raw=raw)
        return

    if not records:
        print("（暂无历史记录，先跑一遍 python main.py 分析 JD）")
        return

    print(f"共 {len(records)} 条，显示最近 {min(limit, len(records))} 条：\n")
    for i, r in enumerate(records[:limit], 1):
        snap = r.get("match_snapshot") or {}
        arch = r.get("advice_archive") or {}
        extras = []
        if "suggestions" in arch:
            extras.append("建议")
        if "interview_pack" in arch:
            extras.append("面试包")
        extra_s = f" | 已生成:{'+'.join(extras)}" if extras else ""

        print(
            f"{i}. [{r.get('jd_id', '')[:8]}…] "
            f"{r.get('company') or '未知公司'} · {r.get('job_title') or '未知岗位'}"
        )
        print(
            f"   匹配分:{_fmt_score(snap)} | 薪资:{r.get('salary') or '—'} | "
            f"分析于:{r.get('analyzed_at') or r.get('created_at') or '—'}{extra_s}"
        )
        if snap.get("top_gaps"):
            gaps = ", ".join(g["missing"] for g in snap["top_gaps"][:2])
            print(f"   主要 gap: {gaps}")
        print(f"   查看详情: python main.py history {i}")
        print()

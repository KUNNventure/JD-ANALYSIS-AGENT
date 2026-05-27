"""T1 JD入库：JDStructured → 本地Chroma（独立JD库，整条存不切片）"""

from dotenv import load_dotenv
load_dotenv()

import json
from datetime import datetime
import chromadb
import dashscope
from schemas.jd import JDStructured


# JD库的本地持久化目录（Agent项目自己的库，独立于RAG项目）
DB_PATH = "./data/jd_db"
COLLECTION_NAME = "jd_collection"

# Chroma客户端：persistent模式 → 数据存本地磁盘，进程重启不丢
_client = chromadb.PersistentClient(path=DB_PATH)
_collection = _client.get_or_create_collection(name=COLLECTION_NAME)


def _embed(text: str) -> list[float]:
    """调DashScope text-embedding-v3，把文本转成向量"""
    resp = dashscope.TextEmbedding.call(
        model="text-embedding-v3",
        input=text,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Embedding调用失败: {resp.message}")
    return resp.output["embeddings"][0]["embedding"]


def _build_embed_text(jd: JDStructured) -> str:
    """
    拼接用于语义搜索的关键文本。只取和岗位内容最相关的字段，不含 raw_text（太长会稀释语义）。
    embed 范围：title + tech_stack + responsibilities；company/salary 仅 metadata。
    """
    parts = [
        jd.job_title,
        " ".join(jd.tech_stack),
        " ".join(jd.responsibilities[:5]),
    ]
    # 过滤掉空字符串再拼接
    return " ".join(p for p in parts if p)


def _loads_json(raw: str, default):
    """metadata 里的 JSON 字符串 → Python 对象。"""
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return default


def _record_from_meta(meta: dict, jd_id: str, score: float | None = None) -> dict:
    """Chroma metadata → 可读 record；兼容旧库 jd_json 格式。"""
    if meta.get("jd_json"):
        legacy = json.loads(meta["jd_json"])
        return {
            "jd_id": jd_id,
            "job_title": legacy.get("job_title", ""),
            "company": legacy.get("company", ""),
            "salary": legacy.get("salary") or meta.get("salary", ""),
            "tech_stack": legacy.get("tech_stack", []),
            "responsibilities": legacy.get("responsibilities", []),
            "match_snapshot": _loads_json(meta.get("match_snapshot", ""), {}),
            "advice_archive": _loads_json(meta.get("advice_archive", ""), {}),
            "company_info": _loads_json(meta.get("company_info", ""), None),
            "analyzed_at": meta.get("analyzed_at", ""),
            "similarity_score": score,
        }
    return {
        "jd_id": jd_id,
        "job_title": meta.get("job_title", ""),
        "company": meta.get("company", ""),
        "salary": meta.get("salary", ""),
        "created_at": meta.get("created_at", ""),
        "analyzed_at": meta.get("analyzed_at", ""),
        "tech_stack": _loads_json(meta.get("tech_stack", "[]"), []),
        "responsibilities": _loads_json(meta.get("responsibilities", "[]"), []),
        "match_snapshot": _loads_json(meta.get("match_snapshot", ""), {}),
        "advice_archive": _loads_json(meta.get("advice_archive", ""), {}),
        "company_info": _loads_json(meta.get("company_info", ""), None),
        "similarity_score": score,
    }


def _get_meta(jd_id: str) -> dict | None:
    result = _collection.get(ids=[jd_id])
    if not result["ids"]:
        return None
    return result["metadatas"][0]


def store_jd(jd: JDStructured) -> str:
    """
    把一条结构化JD存入Chroma。

    Args:
        jd: T1解析出的JDStructured对象
    Returns:
        str: 这条JD的jd_id（用于后续查询）
    """
    # 1. 生成 embedding（基于关键文本）
    embed_text = _build_embed_text(jd)
    embedding = _embed(embed_text)

    # 2. 准备 metadata
    # Chroma 的 metadata 只接受 str/int/float/bool，list 序列化成 JSON 字符串
    existing = _get_meta(jd.jd_id)
    metadata = {
        "job_title": jd.job_title,
        "company": jd.company,
        "created_at": jd.created_at,
        "salary": jd.salary or "",
        "location": jd.location or "",
        "education": jd.education or "",
        "tech_stack": json.dumps(jd.tech_stack, ensure_ascii=False),
        "responsibilities": json.dumps(jd.responsibilities, ensure_ascii=False),
        "company_info": json.dumps(
            jd.company_info.model_dump() if jd.company_info else {},
            ensure_ascii=False,
        ),
        "analyzed_at": existing.get("analyzed_at", "") if existing else "",
        "match_snapshot": existing.get("match_snapshot", "{}") if existing else "{}",
        "advice_archive": existing.get("advice_archive", "{}") if existing else "{}",
    }

    # 3. upsert：同 jd_id 覆盖，保留已有 snapshot/archive
    _collection.upsert(
        ids=[jd.jd_id],
        embeddings=[embedding],
        documents=[embed_text],
        metadatas=[metadata],
    )

    return jd.jd_id


def build_match_snapshot(match_result: dict, resume_fingerprint: str = "") -> dict:
    """T2 结束后写入长期记忆的精简快照（jd_decoded 必存）。"""
    gaps = match_result.get("gaps") or []
    reasons = match_result.get("dimension_reasons") or {}
    return {
        "weighted_total": match_result["weighted_total"],
        "scores": match_result["scores"],
        "below_threshold": match_result["below_threshold"],
        "jd_decoded": reasons.get("jd_decoded", ""),
        "top_gaps": [
            {"missing": g["missing"], "severity": g["severity"]}
            for g in gaps[:3]
        ],
        "resume_fingerprint": resume_fingerprint,
    }


def update_after_t2(jd_id: str, match_snapshot: dict) -> None:
    """T2 结束：更新 match_snapshot，不改 embedding。"""
    meta = _get_meta(jd_id)
    if not meta:
        raise ValueError(f"jd_id 不存在: {jd_id}")
    meta["match_snapshot"] = json.dumps(match_snapshot, ensure_ascii=False)
    meta["analyzed_at"] = datetime.now().isoformat()
    _collection.update(ids=[jd_id], metadatas=[meta])


def update_advice_archive(
    jd_id: str,
    *,
    suggestions: dict | None = None,
    interview_pack: dict | None = None,
) -> None:
    """T3/T4 结束：归档建议，不参与向量检索。"""
    meta = _get_meta(jd_id)
    if not meta:
        raise ValueError(f"jd_id 不存在: {jd_id}")
    archive = _loads_json(meta.get("advice_archive", ""), {})
    if suggestions is not None:
        archive["suggestions"] = suggestions
    if interview_pack is not None:
        archive["interview_pack"] = interview_pack
    meta["advice_archive"] = json.dumps(archive, ensure_ascii=False)
    _collection.update(ids=[jd_id], metadatas=[meta])


def get_jd(jd_id: str) -> JDStructured | None:
    """按 jd_id 精确取回一条 JD（摘要字段）。"""
    meta = _get_meta(jd_id)
    if not meta:
        return None
    if meta.get("jd_json"):
        return JDStructured(**json.loads(meta["jd_json"]))
    rec = _record_from_meta(meta, jd_id)
    return JDStructured(
        jd_id=jd_id,
        job_title=rec["job_title"],
        company=rec["company"],
        salary=rec["salary"] or None,
        tech_stack=rec["tech_stack"],
        responsibilities=rec["responsibilities"],
        created_at=meta.get("created_at", ""),
    )


def get_jd_record(jd_id: str) -> dict | None:
    """取回完整 record（含 match_snapshot / advice_archive），供人工调阅。"""
    meta = _get_meta(jd_id)
    if not meta:
        return None
    return _record_from_meta(meta, jd_id)


def search_jd(query: str, top_k: int = 3, exclude_id: str | None = None) -> list[dict]:
    """
    语义搜索 JD，供 T2 检索历史相似岗。

    Returns:
        list[dict]: record 列表，含 similarity_score 和 match_snapshot
    """
    if not query.strip():
        return []

    n_fetch = top_k + (1 if exclude_id else 0)
    result = _collection.query(
        query_embeddings=[_embed(query)],
        n_results=max(n_fetch, top_k),
    )
    if not result["ids"] or not result["ids"][0]:
        return []

    records = []
    for jd_id, meta, dist in zip(
        result["ids"][0], result["metadatas"][0], result["distances"][0]
    ):
        if exclude_id and jd_id == exclude_id:
            continue
        score = round(1.0 - dist / 2.0, 3)
        records.append(_record_from_meta(meta, jd_id, score=score))
        if len(records) >= top_k:
            break
    return records


def list_all_jd() -> list[JDStructured]:
    """取回库里所有 JD（用于查看历史记录）"""
    result = _collection.get()
    jds = []
    for jd_id, meta in zip(result["ids"], result["metadatas"]):
        jd = get_jd(jd_id)
        if jd:
            jds.append(jd)
    return jds


def list_all_records() -> list[dict]:
    """取回全部 record（含分析快照），按 created_at 倒序。"""
    result = _collection.get()
    records = [_record_from_meta(m, i) for i, m in zip(result["ids"], result["metadatas"])]
    def _sort_key(r: dict) -> str:
        return r.get("analyzed_at") or r.get("created_at") or ""

    return sorted(records, key=_sort_key, reverse=True)


# ====== 单独测试用 ======
if __name__ == "__main__":
    import sys
    from tools.jd_parser import parse_jd

    if len(sys.argv) < 2:
        print("用法: python -m memory.jd_store 图片1.png [图片2.png ...]")
        sys.exit(1)

    jd = parse_jd(sys.argv[1:])
    jd_id = store_jd(jd)
    print(f"已入库 jd_id={jd_id}")

    # 验证：取回 + 搜索
    print("\n=== 精确取回 ===")
    print(get_jd(jd_id).job_title)

    print("\n=== 库内总数 ===")
    print(len(list_all_jd()))

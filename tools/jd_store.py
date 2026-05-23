"""T1 JD入库：JDStructured → 本地Chroma（独立JD库，整条存不切片）"""

from dotenv import load_dotenv
load_dotenv()

import json
import chromadb
import dashscope
from schemas.jd import JDStructured


# JD库的本地持久化目录（Agent项目自己的库，独立于RAG项目）
DB_PATH = "./jd_db"
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
    拼接用于语义搜索的关键文本。
    只取和岗位内容最相关的字段，不含raw_text（太长会稀释语义）。
    """
    parts = [
        jd.job_title,
        jd.company,
        " ".join(jd.tech_stack),
        " ".join(jd.responsibilities),
        " ".join(jd.bonus),
    ]
    # 过滤掉空字符串再拼接
    return " ".join(p for p in parts if p)


def store_jd(jd: JDStructured) -> str:
    """
    把一条结构化JD存入Chroma。

    Args:
        jd: T1解析出的JDStructured对象
    Returns:
        str: 这条JD的jd_id（用于后续查询）
    """
    # 1. 生成embedding(于关键文本）
    embed_text = _build_embed_text(jd)
    embedding = _embed(embed_text)

    # 2. 准备metadata
    # Chroma的metadata只接受 str/int/float/bool，不接受list和dict。
    # 所以list字段(tech_stack等)和dict字段(company_info)要序列化成JSON字符串。
    metadata = {
        "job_title": jd.job_title,
        "company": jd.company,
        "created_at": jd.created_at,
        "salary": jd.salary or "",
        "location": jd.location or "",
        "education": jd.education or "",
        # 整条JD序列化进metadata → 查询时能取回完整对象
        "jd_json": json.dumps(jd.model_dump(), ensure_ascii=False),
    }

    # 3. 存入Chroma
    # document存关键文本（人读得懂查了什么），embedding存向量
    # id用jd_id（schema自动生成的uuid），metadata带完整数据
    _collection.add(
        ids=[jd.jd_id],
        embeddings=[embedding],
        documents=[embed_text],
        metadatas=[metadata],
    )

    return jd.jd_id


def get_jd(jd_id: str) -> JDStructured | None:
    """按jd_id精确取回一条JD"""
    result = _collection.get(ids=[jd_id])
    if not result["ids"]:
        return None
    # 从metadata里反序列化出完整JD对象
    jd_json = result["metadatas"][0]["jd_json"]
    return JDStructured(**json.loads(jd_json))


def search_jd(query: str, top_k: int = 5) -> list[JDStructured]:
    """
    语义搜索JD，如查"LangChain相关岗位"。

    Args:
        query: 自然语言查询
        top_k: 返回数量
    Returns:
        list[JDStructured]: 按相关度排序的JD列表
    """
    query_embedding = _embed(query)
    result = _collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
    )
    # result["metadatas"]是嵌套list（每个query一组结果），取[0]
    jds = []
    for meta in result["metadatas"][0]:
        jds.append(JDStructured(**json.loads(meta["jd_json"])))
    return jds


def list_all_jd() -> list[JDStructured]:
    """取回库里所有JD（用于查看历史记录）"""
    result = _collection.get()
    jds = []
    for meta in result["metadatas"]:
        jds.append(JDStructured(**json.loads(meta["jd_json"])))
    return jds


# ====== 单独测试用 ======
if __name__ == "__main__":
    import sys
    from tools.jd_parser import parse_jd

    if len(sys.argv) < 2:
        print("用法: python -m tools.jd_store 图片1.png [图片2.png ...]")
        sys.exit(1)

    jd = parse_jd(sys.argv[1:])
    jd_id = store_jd(jd)
    print(f"已入库 jd_id={jd_id}")

    # 验证：取回 + 搜索
    print("\n=== 精确取回 ===")
    print(get_jd(jd_id).job_title)

    print("\n=== 库内总数 ===")
    print(len(list_all_jd()))
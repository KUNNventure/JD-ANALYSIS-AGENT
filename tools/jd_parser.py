"""T1 JD解析：多张截图 → Qwen-VL → JDStructured"""

import json
from pathlib import Path

from dotenv import load_dotenv

# 必须在 import dashscope 之前加载 .env（dashscope 在 import 时读取并缓存 DASHSCOPE_API_KEY）
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from dashscope import MultiModalConversation
from schemas.jd import JDStructured


# ====== Prompt：指导模型从截图中提取结构化JD ======
# 要点：
# 1. 明确告诉模型"截图可能乱序"→ 它自己合并，我们不管顺序
# 2. 给出完整JSON模板 → 模型照着填，减少格式出错
# 3. raw_text要求"原样还原" → T3需要原文黑话/语义，结构化会丢
# 4. 提取不到的填null/空列表 → 对应schema里的Optional和默认空list
EXTRACT_PROMPT = """你是一个JD（职位描述）信息提取助手。用户会提供1-5张招聘平台的JD截图。

任务：
1. 截图可能顺序打乱、信息可能不完整，请先理解整体内容再提取
2. 按以下JSON格式提取，提取不到的字段填null或空列表
3. raw_text字段：将截图中JD的完整文字内容原样还原，保留原文措辞和换行

输出严格JSON，不要加```json标记，不要加任何解释文字：
{
    "job_title": "岗位名称",
    "company": "公司名",
    "salary": "薪资，如160-260元/天",
    "location": "工作地点，如广州",
    "work_schedule": "到岗要求，如3天/周 3个月",
    "education": "学历要求",
    "tech_stack": ["技术栈标签1", "技术栈标签2"],
    "responsibilities": ["岗位职责1", "岗位职责2"],
    "requirements": ["任职要求1", "任职要求2"],
    "bonus": ["加分项1", "加分项2"],
    "raw_text": "JD全文原样还原",
    "company_info": {
        "registered_capital": "注册资本",
        "established_date": "成立时间",
        "company_type": "企业类型"
    }
}

注意：如果截图中没有工商信息页，company_info填null。"""


def parse_jd(image_paths: list[str]) -> JDStructured:
    """
    多张JD截图 → 调Qwen-VL-Plus → 返回JDStructured对象

    Args:
        image_paths: 图片文件路径列表（支持jpg/png）
    Returns:
        JDStructured: 结构化JD数据（含jd_id和created_at，由schema自动生成）
    """

    # === 第1步：构建多模态消息 ===
    # 所有图片 + prompt 放进同一条消息，一次性发给模型
    # DashScope 用 file:// 协议读本地文件，不需要手动转base64
    content = []
    for path in image_paths:
        abs_path = str(Path(path).resolve())
        content.append({"image": f"file://{abs_path}"})

    content.append({"text": EXTRACT_PROMPT})

    messages = [{"role": "user", "content": content}]

    # === 第2步：调用 Qwen-VL-Plus ===
    response = MultiModalConversation.call(
        model="qwen-vl-plus",
        messages=messages,
    )

    # 检查调用是否成功
    if response.status_code != 200:
        raise RuntimeError(
            f"Qwen-VL调用失败: code={response.status_code}, "
            f"message={response.message}"
        )

    # === 第3步：提取模型返回的文本 ===
    raw_output = response.output.choices[0].message.content[0]["text"]

    # === 第4步：清理 + 解析JSON ===
    # 模型有时会加```json...```包裹，需要去掉
    cleaned = raw_output.strip()
    if cleaned.startswith("```"):
        # 去掉第一行的 ```json
        cleaned = cleaned.split("\n", 1)[1]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    data = json.loads(cleaned)

    # === 第5步：用Pydantic校验，生成JDStructured ===
    # jd_id 和 created_at 由schema的default_factory自动生成，不需要模型输出
    jd = JDStructured(**data)

    return jd


# ====== 单独测试用 ======
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法: python -m tools.jd_parser 图片1.png [图片2.png ...]")
        sys.exit(1)

    result = parse_jd(sys.argv[1:])
    # .model_dump() 是 Pydantic v2 的方法，把对象转成字典
    print(json.dumps(result.model_dump(), ensure_ascii=False, indent=2))
"""T4 工具：模拟面试包。

职责：基于 JD + gap 清单，一次性生成：
  1. 模拟面试题（技术题 + 项目题 + 场景题）
  2. 参考答案要点
  3. 面试准备建议

设计决策：
  - demo 版，一个 prompt 出全部内容，不做题库管理、不挂 Bad Case 回归
  - 题目围绕 gap 出——面试官大概率追问你薄弱的地方
"""
import json
from dashscope import Generation

STRONG_MODEL = "qwen-max"

INTERVIEW_PROMPT = """你是一位资深的 AI 应用开发方向技术面试官，正在为一位候选人准备模拟面试。

你会拿到两份材料：
1. 结构化 JD（岗位要求）
2. T2 匹配分析结果（含 gap 清单、匹配分数、JD 黑话翻译）

请生成一套模拟面试包。

【模拟面试题】
生成 6-8 道面试题，分三类：
1. 技术八股题（2-3 道）：围绕 JD 技术栈里候选人可能被问到的基础概念
   - 优先从 gap 清单里 severity=high/mid 的技术点出题
   - 如果 gap 不多，从 JD 核心技术栈里挑高频面试题
2. 项目深挖题（2-3 道）：模拟面试官追问候选人简历项目的场景
   - "你的 XX 项目里，为什么选 A 不选 B？"
   - "遇到 XX 问题你怎么解决的？"
3. 场景题（2 道）：给一个和 JD 职责相关的实际场景，问候选人怎么设计/解决
   - 不要太抽象，给具体约束条件

每道题需要：
  - category: "technical" / "project" / "scenario"
  - question: 题目
  - key_points: 参考答案要点（3-5 个要点，不是完整答案）
  - why: 为什么问这道题（对应 JD 的什么要求或 gap 的什么缺口）

【面试准备建议】
给出 3-4 条针对这个岗位的面试准备建议。
要求具体可执行，比如"重点准备 XX 的讲法，能讲清楚 A vs B 的 trade-off"，
不要给"好好准备""保持自信"这种废话。

【输出格式】
注意：不要重复生成相同的题目，每道题必须不同。生成完 6-8 道后立即停止。
严格输出 JSON，不要加 ```json 标记，不要加任何解释文字：
{{
  "questions": [
    {{
      "category": "technical",
      "question": "题目",
      "key_points": ["要点1", "要点2"],
      "why": "出题理由"
    }}
  ],
  "prep_advice": [
    "建议1",
    "建议2"
  ]
}}

【JD 结构化信息】
{jd_block}

【T2 匹配分析结果】
{match_block}
"""


def _build_prompt(jd_structured: dict, match_result: dict) -> str:
    jd_block = json.dumps(jd_structured, ensure_ascii=False, indent=2)
    match_block = json.dumps(match_result, ensure_ascii=False, indent=2)
    return (INTERVIEW_PROMPT
            .replace("{jd_block}", jd_block)
            .replace("{match_block}", match_block))


def _call_llm(prompt: str) -> dict:
    """调强模型，返回解析后的 dict。"""
    resp = Generation.call(
        model=STRONG_MODEL,
        messages=[{"role": "user", "content": prompt}],
        result_format="message",
        temperature=0.7,   # 面试题需要一定多样性
    )
    if resp.status_code != 200:
        raise RuntimeError(f"千问调用失败: {resp.code} {resp.message}")
    text = resp.output.choices[0].message.content.strip()
    text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(text)


def generate_interview_pack(jd_structured: dict, match_result: dict) -> dict:
    """T4 核心：输入 JD + 匹配结果，输出模拟面试包。

    返回结构（写进 state["interview_pack"]）：
      questions    模拟题列表（含分类、题目、答案要点、出题理由）
      prep_advice  面试准备建议列表
    """
    prompt = _build_prompt(jd_structured, match_result)
    return _call_llm(prompt)
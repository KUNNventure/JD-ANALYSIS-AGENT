"""T3 工具：求职准备建议。

职责：基于 T2 匹配结果 + JD 原文 + 简历，生成针对性的：
  1. 招呼语（投递时发给 HR/负责人的开场白）
  2. 简历修改建议（针对这份 JD 该突出/补充什么）
  3. 交流建议（投递后沟通的注意事项）
  4. 公司/岗位画像 + 是否值得投（原 T2 第五步、第六步合并到此）

设计决策：
  - T3 输入保留 JD 原文（jd_structured），不只用 gap 清单——结构化会丢黑话/语义
  - 一次 LLM 调用出三块内容，不拆子链路
"""
import json
from dashscope import Generation
from tools.company_context import format_company_block

STRONG_MODEL = "qwen-max"

ADVICE_PROMPT = """你是一位资深的求职辅导顾问，正在帮一位大三学生准备投递一个大模型应用开发实习岗位。

你会拿到三份材料：
1. 结构化 JD（岗位要求）
2. T2 匹配分析结果（含匹配度分数、gap 清单、JD 黑话翻译）
3. 求职者简历

请完成以下四个任务。

【任务一：写招呼语】
写一段 80-150 字的投递招呼语，用于在 Boss 直聘等平台发给 HR 或技术负责人。
要求：
  - 开头不要用"X总您好"这种套路，用自然的打招呼方式
  - 点明你对这个岗位/方向的真实兴趣（结合 JD 里的具体职责，不要泛泛说"贵公司"）
  - 用 1-2 句话点出你最匹配的经验（从简历里挑最对口的）
  - 主动提及可实习时长（简历里有）
  - 不要吹牛，不要用"深耕""赋能"等空话

【任务二：简历修改建议】
针对这份 JD，给出 3-5 条具体的简历修改建议。
每条需要：
  - point: 一句话建议
  - reason: 为什么改（对应 JD 的哪个要求或 gap）
  - how: 怎么改（给出具体可操作的修改方向，不要只说"突出XX"）
优先级：先补 gap 里 severity=high 的，再补 mid 的。

【任务三：交流建议】
给出 3-4 条投递后与 HR/面试官沟通的建议。
要求针对这个具体岗位的特点（不要给泛泛的"保持礼貌"之类的废话），
比如：该主动提什么、该避免什么、该准备什么问题问面试官。

【任务四：公司/岗位画像 + 是否值得投（结合下方工商信息）】
参考【公司/工商信息】。有注册资本、成立时间等数据时优先依据数据；没有则据 JD 与公司名推断，并注明「推断」。
  company_profile.summary: 岗位 + 公司整体画像（一段话）
  company_profile.signals: 3-5 条参考信号（规模、方向、风险等）
  company_viability.verdict: recommend | caution | insufficient_data
  company_viability.reasons: 2-4 条具体理由
  company_viability.red_flags: 风险点列表，没有则 []

【公司/工商信息】
{company_block}

【输出格式】
严格输出 JSON，不要加 ```json 标记，不要加任何解释文字：
{{
  "greeting": "招呼语正文",
  "resume_advice": [
    {{"point": "建议", "reason": "原因", "how": "具体怎么改"}}
  ],
  "communication_advice": [
    "建议1",
    "建议2"
  ],
  "company_profile": {{"summary": "公司画像", "signals": ["信号1"]}},
  "company_viability": {{
    "verdict": "recommend",
    "reasons": ["理由1"],
    "red_flags": []
  }}
}}

【JD 结构化信息】
{jd_block}

【T2 匹配分析结果】
{match_block}

【求职者简历】
{resume_block}
"""


def _build_prompt(jd_structured: dict, match_result: dict, resume) -> str:
    jd_block = json.dumps(jd_structured, ensure_ascii=False, indent=2)
    match_block = json.dumps(match_result, ensure_ascii=False, indent=2)
    resume_block = (
        resume if isinstance(resume, str)
        else json.dumps(resume, ensure_ascii=False, indent=2)
    )
    company_block = format_company_block(jd_structured)
    return (ADVICE_PROMPT
            .replace("{jd_block}", jd_block)
            .replace("{match_block}", match_block)
            .replace("{resume_block}", resume_block)
            .replace("{company_block}", company_block))


def _call_llm(prompt: str) -> dict:
    """调强模型，返回解析后的 dict。和 jd_matcher 同一套路。"""
    resp = Generation.call(
        model=STRONG_MODEL,
        messages=[{"role": "user", "content": prompt}],
        result_format="message",
        temperature=0.7,   # 建议类内容稍高温度，更自然
    )
    if resp.status_code != 200:
        raise RuntimeError(f"千问调用失败: {resp.code} {resp.message}")
    text = resp.output.choices[0].message.content.strip()
    text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(text)


def generate_advice(jd_structured: dict, match_result: dict, resume) -> dict:
    """T3 核心：输入 JD + 匹配结果 + 简历，输出求职准备建议。

    返回结构（写进 state["suggestions"]）：
      greeting / resume_advice / communication_advice
      company_profile / company_viability
    """
    prompt = _build_prompt(jd_structured, match_result, resume)
    return _call_llm(prompt)
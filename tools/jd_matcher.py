"""T2 工具：简历-JD 匹配。

职责：
  1. 个人维度 + 岗位维度 两维打分（强模型判断）
  2. 加权总分 + 阈值判断（纯 Python，可复现）
  3. 公司画像分析（独立信息呈现，不打分、不计入总分）

executor 会以 t2(state) 调用 t2_node（见文件末尾），返回值写进 state["match_result"]。
"""
import json
import dashscope
from dashscope import Generation

# ========== 可调参数（改这里即可，每次改记进 DECISIONS.md）==========
WEIGHTS = {"personal": 7, "job": 3}   # 个人:岗位 = 5:3，公司维度不计分
THRESHOLD = 60                         # 加权总分 < 此值 → 触发 human-in-the-loop
STRONG_MODEL = "qwen-max"                # 强模型；千问max

# ========== 给强模型的提示词 ==========
MATCH_PROMPT = """你是一个资深的技术招聘顾问，正在帮一位求职者评估他与某个岗位的匹配度。

你会拿到两份材料：一份结构化的 JD，一份求职者简历。请完成以下分析。

【第一步：翻译 JD 黑话】
JD 的字面描述往往不等于真实要求。先把岗位职责和任职要求翻译成"真正想要什么样的人"。
例如：
  "对接业务部门" → 需要跨团队沟通能力，能和非技术人员讲清需求
  "快速迭代 / 拥抱变化" → 工作节奏快，需要抗压和容错能力
  "独立负责模块" → 要求能独立推进，不靠人带

【第二步：个人维度打分（0-100）】
拿求职者的简历，对比 JD 的硬性要求。从以下三个子项综合判断：
  1. 技术栈覆盖：JD 的 tech_stack / requirements 里要求的技术，简历命中多少、缺哪些
  2. 项目对口度：简历项目所做的事，与 JD 职责的实际重合度（不只看技术名词，看做过的事像不像）
  3. 经验/学历硬门槛：JD 的 education 和经验要求（如"X年经验""相关实习"），简历是否满足
给出综合分数和理由，理由需点明：技术栈命中情况、最对口的项目、是否有硬门槛不满足。

【第三步：岗位维度打分（0-100）】
岗位维度不评估求职者软实力（简历无法支撑），只判断"这个岗位想要的人，和求职者是不是同一类人"。
从以下三个可客观判断的点打分：
  1. 画像方向：JD 想要研究型还是工程落地型人才？与求职者经历画像是否同方向
  2. 真实重心：JD 职责的核心比重落在哪（如 Agent 开发 / RAG / 前端）？与简历主项目重心是否吻合
给出分数和一句话理由，理由需点明三点中哪些吻合、哪些不吻合。

【第四步：列出 gap 清单】
列出求职者相比 JD 要求缺失或薄弱的点。每条标注：
  dimension: personal（能力缺口）或 job（工作方式 / 软性缺口）
  missing: 具体缺什么
  severity: high（硬性要求不满足）/ mid（加分项缺失）/ low（锦上添花）
  重要：列 gap 前，必须逐条在简历全文中检索该项是否已具备。简历"专业技能"段落里出现的能力，不得列为缺失。只列简历中确实找不到证据的项。

【第五步：岗位与公司整体画像（仅信息呈现，不打分）】
对那些边界模糊、不适合硬性打分的部分，做结构化呈现而非评分：
  overview: 一段话概括这个岗位 + 公司整体是什么样的
  what_they_want: 提炼 JD 真实想要的人才特征（3-5 条）
  notes: 其他对求职者有参考价值的信号——硬过滤条件（届别 / 线下城市 / 实习时长）、公司规模、成立时间、行业方向、学历倾向、潜在风险点等

【输出格式】
严格输出 JSON，不要加 ```json 标记，不要加任何解释文字：
{
  "personal": {"score": 整数, "reason": "一句话理由"},
  "job": {"score": 整数, "reason": "一句话理由", "jd_decoded": "JD 黑话翻译总结"},
  "gaps": [
    {"dimension": "personal", "missing": "具体缺什么", "severity": "high"}
  ],
  "company_profile": {"summary": "公司画像描述", "signals": ["信号1", "信号2"]}
}

【JD 结构化信息】
{jd_block}

【求职者简历】
{resume_block}
"""


def _build_prompt(jd_structured: dict, resume) -> str:
    """把 JD 字典和简历拼进提示词模板。

    resume 可能是 dict（AgentState 里的类型）或 str，两种都兼容。
    """
    jd_block = json.dumps(jd_structured, ensure_ascii=False, indent=2)
    resume_block = (
        resume if isinstance(resume, str)
        else json.dumps(resume, ensure_ascii=False, indent=2)
    )
    return MATCH_PROMPT.replace("{jd_block}", jd_block).replace(
        "{resume_block}", resume_block
    )


def _call_llm(prompt: str) -> dict:
    """调强模型（千问 qwen-max），返回解析后的 dict。

    用 result_format='message' 拿标准消息结构；
    千问不强制 JSON，靠 prompt 约束 + 兜底剥围栏。
    """
    resp = Generation.call(
        model=STRONG_MODEL,
        messages=[{"role": "user", "content": prompt}],
        result_format="message",
        temperature=0.3,   # 评估任务要稳定，低温度
    )
    if resp.status_code != 200:
        raise RuntimeError(f"千问调用失败: {resp.code} {resp.message}")
    text = resp.output.choices[0].message.content.strip()
    text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(text)

def _weighted_total(personal: int, job: int) -> float:
    """加权总分。算术留在 Python：可复现、可测试、被问"权重怎么调"能现场改。"""
    total_weight = WEIGHTS["personal"] + WEIGHTS["job"]   # 7 + 3 = 10
    raw = personal * WEIGHTS["personal"] + job * WEIGHTS["job"]
    return round(raw / total_weight, 1)


def match_jd(jd_structured: dict, resume) -> dict:
    """T2 核心：输入结构化 JD + 简历，输出匹配分析。

    返回结构（会被写进 state["match_result"]）：
      scores            两维原始分
      weighted_total    加权总分（Python 算）
      below_threshold   是否低于阈值（Python 判，用于触发 human-in-the-loop）
      gaps              gap 清单（传给 T3）
      dimension_reasons 每维度理由 + JD 黑话翻译
      company_profile   公司画像（不计分，仅呈现）
    """
    prompt = _build_prompt(jd_structured, resume)
    llm_out = _call_llm(prompt)

    personal_score = llm_out["personal"]["score"]
    job_score = llm_out["job"]["score"]
    total = _weighted_total(personal_score, job_score)

    return {
        "scores": {"personal": personal_score, "job": job_score},
        "weighted_total": total,
        "below_threshold": total < THRESHOLD,
        "gaps": llm_out["gaps"],
        "dimension_reasons": {
            "personal": llm_out["personal"]["reason"],
            "job": llm_out["job"]["reason"],
            "jd_decoded": llm_out["job"]["jd_decoded"],
        },
        "company_profile": llm_out["company_profile"],
    }


"""4个工具的mock版本，骨架阶段用，返回假数据。
字段结构对齐设计文档的T1-T4输出定义，Day3起逐个替换为真实现。"""


def mock_t1(state):
    """T1 JD解析入库：多张JD截图 → 结构化JD"""
    return {
        "company": "示例科技有限公司",
        "tech_stack": ["Python", "LangChain", "RAG"],
        "experience": "实习/应届",
        "responsibilities": ["搭建Agent应用", "优化检索效果"],
        "education": "本科及以上",
        "bonus": ["有开源项目", "熟悉MCP"],
    }

def mock_t2(state):
    """T2 简历-JD匹配：JD + 简历 → 三维匹配度 + gap清单"""
    return {
        "personal_score": 75,
        "position_score": 68,
        "company_score": 80,
        "weighted_score": 73,
        "gap": ["缺少向量库调优经验", "无线上部署经历"],
    }


def mock_t3(state):
    """T3 求职准备建议：匹配度 + gap + JD原文 → 建议"""
    return {
        "greeting": "X总您好，我对贵公司的Agent开发岗位很感兴趣……",
        "resume_advice": ["项目描述补充量化指标", "突出MCP相关经验"],
        "communication_advice": ["主动提及可实习时长"],
    }


def mock_t4(state):
    """T4 模拟面试包：JD + gap → 模拟题 + 答案 + 准备建议"""
    return {
        "questions": ["讲讲你对RAG链路的理解", "LangGraph和LangChain的区别"],
        "reference_answers": ["RAG链路包括切片、向量化……", "LangChain偏链式……"],
        "prep_advice": ["重点准备Bad Case分析的讲法"],
    }
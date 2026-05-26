# 项目开发进度日志

## Day 1 - 设计
做了：定项目方案——JD分析Agent（输入JD截图→三维匹配→求职建议+模拟面试包），
产出设计文档、架构图、时间流程表。确定技术栈：LangGraph + Plan-Execute + MCP复用RAG，4个工具（T1解析/T2匹配/T3建议/T4面试包）。
决策：编排框架选 LangGraph、控制范式选 Plan-Execute、RAG以MCP复用。

## Day 2 - 骨架
做了：搭完 LangGraph 骨架——AgentState（TypedDict）、4个mock工具、
Planner-Executor 节点、StateGraph 组装+条件路由，main.py 空跑通过
（planner→executor×4→END），4工具产出字段全部正确，。
坑：① Cursor Agent 连不上——VPN 常用节点不稳，更改节点之后Agent断线，改用Claude生成代码。
决策：DECISIONS.md 记录 TypedDict vs MessageGraph、Plan-Execute vs ReAct，LangChain vs LangGraph三条选型。

## Day 3 — T1 JD解析入库完成
Qwen-VL多模态解析JD截图 → JDStructured → 本地Chroma入库，已替换mock_t1接进Agent，端到端真实跑通T1。
踩坑：① requirements.txt带hash校验导致chromadb装不上，改用 pip install chromadb 单独装；② .env的key在新终端会丢，加 load_dotenv() 从.env读取。
遗留：tech_stack混入了经验类描述（"后端开发经验"等），Day10优化prompt时处理。

## Day 4 - T2 简历-JD匹配
做了：实现 T2（jd_matcher.py 实现 + t2.py 节点），两维加权打分跑通。
踩坑：① Karing 全局代理（端口3067）导致 dashscope 上传图片到 OSS 被掐断，
报 ProxyError/ConnectionReset → 用 requests.Session.trust_env=False 让 requests
忽略代理直连国内 OSS 解决。② tests/ 子目录脚本 import 不到 tools 包 →
sys.path 插入项目根目录解决。③ gap 误判：模型漏读简历"专业技能"段，
把已具备的 AI Coding 工具列为缺失 → prompt 加"列 gap 前逐条核对简历全文"约束修复。
优化：T1 产出缓存为 tests/jd_sample.json，后续测 T2 不再跑 T1、不碰网络。

## Day 5 - T3/T4实现，完整链路跑通输出正常，三条分支全部验证通过。
正常推进（分支1）：端到端跑通，匹配总分80.5，T1-T4全链路输出正常。
失败重规划（分支2）：T3注入异常，重试3次后degrade跳过，T4照常执行。
human-in-the-loop（分支3）：阈值调至90触发interrupt，暂停输出分数+gap，y/n恢复正常。
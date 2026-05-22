# 项目开发进度日志

## Day 1 · 设计
做了：定项目方案——JD分析Agent（输入JD截图→三维匹配→求职建议+模拟面试包），
产出设计文档、架构图、时间流程表。确定技术栈：LangGraph + Plan-Execute +
MCP复用RAG，4个工具（T1解析/T2匹配/T3建议/T4面试包）。
决策：编排框架选 LangGraph、控制范式选 Plan-Execute、RAG以MCP复用。

## Day 2 · 骨架
做了：搭完 LangGraph 骨架——AgentState（TypedDict）、4个mock工具、
Planner-Executor 节点、StateGraph 组装+条件路由，main.py 空跑通过
（planner→executor×4→END），4工具产出字段全部正确，。
坑：① Cursor Agent 连不上——VPN 常用节点不稳，更改节点之后Agent断线，改用Claude生成代码。

决策：DECISIONS.md 记录 TypedDict vs MessageGraph、Plan-Execute vs ReAct，LangChain vs LangGraph三条选型。
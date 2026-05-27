# 项目开发进度日志

## Day 1 - 设计
做了：定项目方案——JD分析Agent（输入JD截图→匹配→求职建议+模拟面试包），
产出设计文档、架构图、时间流程表。技术栈初定：LangGraph + Plan-Execute + 4 工具（T1解析/T2匹配/T3建议/T4面试包）。
决策：编排框架选 LangGraph、控制范式选 Plan-Execute。（JD 库后改为自建 Chroma，未复用 RAG MCP，见 Day 6 / DECISIONS）

## Day 2 - 骨架
做了：搭完 LangGraph 骨架——AgentState（TypedDict）、4 个 mock 工具、
Planner-Executor 节点、StateGraph 组装 + 条件路由，main.py 空跑通过
（planner→executor×4→END），4 工具产出字段全部正确。
坑：① Cursor Agent 连不上——VPN 节点不稳，改用 Claude 生成代码。
决策：DECISIONS.md 记录 TypedDict vs MessageGraph、Plan-Execute vs ReAct、LangChain vs LangGraph。

## Day 3 — T1 JD 解析入库
做了：Qwen-VL 多模态解析 JD 截图 → JDStructured → 本地 Chroma 入库，替换 mock_t1，端到端跑通 T1。
踩坑：① requirements.txt 带 hash 导致 chromadb 装不上，改 pip install chromadb；② .env 在新终端丢失，加 load_dotenv()。
遗留：tech_stack 混入经验类描述，后续优化 T1 prompt。

## Day 4 - T2 简历-JD 匹配
做了：实现 T2（jd_matcher + tool_defs），两维加权打分跑通。
踩坑：① 代理导致 dashscope 上传 OSS 失败 → trust_env=False；② tests 子目录 import → sys.path 插根目录；
③ gap 漏读简历「专业技能」→ prompt 加「列 gap 前逐条核对全文」。
优化：T1 产出缓存 tests/jd_sample.json，测 T2 可不跑 T1。

## Day 5 - T3/T4 + 三条分支
做了：T3/T4 接入，完整链路跑通。
验证：
- 分支1 正常推进：T1→T4 输出正常（示例加权总分 80.5）。
- 分支2 失败处理：T3 注入异常，同一步重试 3 次 → degrade → Planner 重出 plan。
- 分支3 human-in-the-loop：调高阈值触发 interrupt，y/n 恢复正常。

## Day 6 - 优化清单必做项 + 记忆模块 + 目录整理
对照《优化点清单》完成必做 3 项，并落地长期/短期记忆。

### 6.1 LLM 动态 Planner
- 原状：plan 写死 `["T1","T2","T3","T4"]`。
- 现况：`agent/nodes.py` 调 qwen-max，读 `user_request` 输出工具序列；支持「只匹配」「不要 T4」等。
- 降级：LLM 失败或 JSON 解析失败 → 回退全流程。
- 重规划：带 `last_tool_error` 时 Planner 可改 plan、跳过无依赖工具。

### 6.2 失败处理措辞与实现
- 区分：**同一步重试**（retry_count≤3，不改 plan）vs **交 Planner 重规划**（degrade→planner，replan_count≤2）。
- 图：`agent/graph.py` 三分支注释已与实现一致；DECISIONS 同步。

### 6.3 向量库「只写不读」→ T2 读库
- `memory/jd_store.py`：T1 upsert JD 摘要；T2 前 `search_jd` 检索历史；T2 后 `update_after_t2` 写 `match_snapshot`（含 **jd_decoded**）。
- `tools/jd_matcher.py`：历史相似岗注入 prompt；`state.similar_jds` 写入当次上下文。
- T3/T4 结果写入 `advice_archive`，**不参与 embed/检索**，仅供调阅。

### 6.4 记忆模块架构
- **长期 JD**：Chroma `./data/jd_db`，embed = title + tech_stack + responsibilities；metadata 含 salary、match_snapshot、advice_archive。
- **长期简历**：SQLite `./data/jd_db/resume.sqlite`，fingerprint 版本链；`main.py` 启动 `load_resume` / 空库时 seed `resume.md`。
- **短期**：AgentState 传当次全量（含 raw_text）；MemorySaver 仅 interrupt 断点续跑。

### 6.5 目录拆分
- `agent/`：graph、nodes、state（编排）
- `memory/`：jd_store、resume_store（持久化）
- `tools/`：T1–T4 实现与 tool_defs
- `docs/`：DECISIONS、DEV_LOG

### 遗留（加分项，未做）
- Bad Case 回归集（清单 #4）
- T1 qwen-vl-plus vs max 成本/质量对比表（清单 #5）

### 6.6 Checker 接入 graph
- 流程：`executor` 成功 → `checker` 校验 T1/T2 关键字段 → 再路由
- T1 缺字段：自动重试一次 → 仍缺则 interrupt 问用户
- human-in-the-loop 改为按「刚跑完的是不是 T2」判断，不再写死 `current_step==2`

### 6.7 终端体验抛光
- `main.py`：每次 run 新 `thread_id`；`--images` / `--request`；history 懒加载
- `executor`：▶/✓ 进度 + 耗时 + 一步摘要；重规划 `_resume_step` 跳过已完成工具
- T1 interrupt 展示 `image_paths`；`history --id` 分块可读，`--raw` 看全量 JSON

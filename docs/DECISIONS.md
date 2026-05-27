### 决策记录

# 为什么状态文件用 TypedDict 不用 MessageGraph
MessageGraph 的 state 是一串固定的消息列表（一条条信息依次往列表里追加），存不了 jd_structured、match_result 这种结构化中间结果。项目的 Agent 要在 state 里存四个工具的产物，必须自定义结构化字段，所以用 TypedDict。

# Plan-Execute vs ReAct :
Plan-Excute模式先规划好流程路线，再调用工具进行具体执行；ReAct模式按Thought-Action-Observation循环进行进行推进，观察每一步的结果决定下一步的行动。
两者各有优劣：Plan适合流程相对固定的任务如coding Agent，但如果某个环节失败不好调整（需要引入重规划），ReAct适合流程每步产出随机性高，比较灵活的任务，比如deepresearch Agent，但缺点是控制性弱，成本高。
对于本项目，JD解析 匹配度分析 初步行动建议 面试包 四个环节在流程中位置明确，前后联系紧密，用Plan模式能够达到比较好的效果，ReAct模式的灵活性在这个场景中属于冗余特性，且成本更高，选取前者作为最终实现

## 为什么编排框架选型用 LangGraph 而非 LangChain（chain 抽象）
LangChain 的核心是 Chain——把「调 LLM→解析→再调」打包成高层抽象，流程是有向无环链，state 以消息列表为主。LangGraph 提供节点、边、状态三个原语，流程可成图（含循环和条件分支）、state 可自定义。
选 LangGraph 的三个结构性需求：① 失败时需循环（同一步重试、或回 Planner 重出 plan）；② 结构化中间状态（jd_structured、match_result 等）；③ 条件路由（T2 低分 human-in-the-loop）。
内置 interrupt + checkpointer 用于断点续跑，自研成本高。
一句话：LangGraph 是图状态机，把控制流暴露给业务代码，适合 Plan-Execute Agent。

## Planner 用 LLM 动态规划（替代写死 plan）
决策：Planner 调 qwen-max，读 `user_request` + 工具说明，输出 JSON 数组如 `["T1","T2"]` 或 `["T1","T2","T3","T4"]`。
原因：用户说「只帮我匹配」「不要面试题」时，写死全流程会多跑无用工具；面试需能讲清「Planner 怎么规划」。
规则（prompt）：默认全流程；显式用户意图可裁剪；尊重 T1→T2→(T3/T4) 依赖；T3/T4 互不依赖可只选其一。
降级：API 失败或 JSON 非法 → 回退 `["T1","T2","T3","T4"]`。
重规划：degrade 后再次进入 Planner 时附带 `last_tool_error`；`current_step` 由代码按 state 已有产物跳到 plan 内第一个未完成工具（不盲归零）。
追问准备：和「固定工作流」的区别？→ 计划是 LLM 按请求生成的，不是 if-else 写死的四条链路。

## 失败处理：同一步重试 vs 交 Planner 重规划
决策：工具失败分两档，措辞上区分「重试」与「重规划」。
- **同一步重试**：`retry_count++`，路由回 executor 再跑同一步（最多 3 次），**不改 plan**。
- **重试耗尽**：`degrade` → `planner`，带 `last_tool_error` **重新出 plan**；`replan_count` 达 2 则 `plan=[]` 终止。
- 重规划时是否跳过某工具：由 Planner LLM 根据依赖决定，不在 degrade 里写死「跳过 T4」等逻辑。
原因：简历/面试须诚实——不是「一失败就叫重规划」，而是「先同参数重试，再重出计划」。
实现：`agent/graph.py` 分支2；`agent/state.py` 中 `retry_count` 与 `replan_count` 分字段。
追问准备：旧文档写 degrade 跳过？→ 已改为统一交 Planner，见 DEV_LOG Day 6.2。

## 多模态直接抽取，不用 OCR
决策：JD 截图直接喂 Qwen-VL，按 schema 结构化抽取，不走 OCR→拼接→纠错链路。
原因：OCR 不理解版式；多模态一步到位理解「职责/要求/标签区」。JD 版式杂，正是多模态强项。
追问准备：多图顺序/冲突？→ 多图同一次调用，模型自行合并；抽不到字段靠 Optional / 默认空 list。

## JD 库独立，不复用 RAG 项目的 MCP
决策：JD 分析 Agent 自建本地 Chroma 库，不通过 MCP 调 RAG 项目入库。
原因：
RAG 项目的能力是"切片 → 召回 → 重排 → 增强生成"，为问答场景设计。
JD 库的需求只有两点：整条存（不切片）+ 语义检索取回。用不上 RAG 的切片/召回/增强生成链路。
强行复用 = 把简单需求套进重链路，反而增加耦合和复杂度。
JD 库定位：长期记忆。每条 JD 存摘要 + match_snapshot + advice_archive；T2 检索历史辅助打分。
对比：复用 RAG-MCP = 跨项目依赖 + 用不上的能力；独立 Chroma = 自给自足、接口可控。
追问准备：能讲清"RAG 和向量库不是一回事"——RAG 是一套检索增强生成的方法链，向量库只是其中的存取组件；本项目只需要后者。

## 长期记忆 vs 短期记忆
决策：**长期** = Chroma（JD）+ SQLite（简历）；**短期** = AgentState + MemorySaver（仅 interrupt）。
| 层级 | 存储 | 内容 | 谁读写 |
|------|------|------|--------|
| 长期 JD | `memory/jd_store` / `./data/jd_db` | 摘要字段 + match_snapshot + advice_archive | T1 写；T2 检索+写 snapshot；T3/T4 写 archive |
| 长期简历 | `memory/resume_store` / resume.sqlite | 简历全文版本链 + fingerprint | main 启动加载最新；snapshot 记 fingerprint |
| 短期工作记忆 | AgentState | 当次 jd_structured（含 raw_text）、match_result、similar_jds 等 | 工具链传递 |
| 会话断点 | MemorySaver | interrupt 暂停时的 state | y/n 恢复，非跨 JD 历史 |

**T2 检索用什么（注入 prompt，非 embed）：** 历史记录的 job_title、company、salary、match_snapshot（**jd_decoded**、上次分数、top_gaps）、相似度。**不检索** advice_archive。
**embed 文本：** job_title + tech_stack + responsibilities（前几条）。不含 company/salary/bonus/raw_text。
**写入时机：** T1 → JD 摘要；T2 结束 → match_snapshot；T3/T4 结束 → advice_archive（不更新向量）。
**T2 为何参考历史：** 校准黑话理解与打分锚点，解决「向量库只写不读」；非照搬旧分（prompt 约束「禁止直接抄分」）。
目录：`agent/` 编排，`memory/` 持久化，`tools/` 业务工具。

## 模型分级：T1 用弱模型 Qwen-VL-Plus
决策：T1 抽取用 qwen-vl-plus（弱多模态），Planner + T2/T3/T4 用强模型。
原因：
T1 是"照着 schema 填空"的结构化抽取，不需要推理，弱模型足够。
plus 比 max 便宜，MVP 阶段够用；和 RAG 项目同平台（DashScope），同一 API key，省一次选型。
对比：全程强模型 = 成本高且 T1 用不上推理能力；分级 = 省成本，Day10 出"分级 vs 全强模型"成本对比数据。

## embedding 选 text-embedding-v3
决策：JD 库 embedding 用 DashScope text-embedding-v3。
embed 范围见「长期记忆 vs 短期记忆」；T3/T4 archive 只存档、不参与 embed。

## T2 从三维打分演进为二维（个人7 : 岗位3），公司维度下沉 T3

**演进过程（避免 README 与旧文档「三维」表述打架）：**

| 阶段 | 方案 | 问题 |
|------|------|------|
| 初版 | 个人5 : 岗位3 : 公司1.5 三维加权 | 公司分依赖「用户偏好」（规模、融资、城市等），MVP 无采集入口，硬打分易误导 |
| 调整 | 岗位维拆出「隐藏门槛」等不可可靠判断项 → 移入 profile，岗位只保留 2 个可证据化子项 | 岗位可打分子项变少，原 5:3 权重需重标定 |
| 现版 | **T2 仅个人+岗位 7:3**；公司信息在 **T3** 以 `company_profile` / `company_viability` **定性呈现，不计入 weighted_total** | 打分链路可复现；公司判断不冒充客观分数 |

**为什么砍公司维打分（而不是先做个默认分）：**
- 没有用户偏好数据时，模型对公司好坏的判断主观且不可对标，容易和 T2 人岗分混淆决策。
- 「投不投」主要由人岗匹配决定；公司是否值得去，更适合在 T3 结合 JD/公开信息给 **recommend / caution** 类结论，而非和技能分加在一起。

**为什么岗位从原 5:3 调到 7:3：**
- 个人维度（硬技能/项目 vs JD 硬性要求）对「要不要投」影响最大。
- 岗位维可证据化项减少后，若仍占 3 份权重，会放大噪声；收敛为 7:3 更贴近「技能匹配为主、岗位语境为辅」。

**README 与代码一致点：** `tools/jd_matcher.py` 中 `WEIGHTS = {"personal": 7, "job": 3}`，无 company 键；公司相关内容见 `tools/job_advisor.py`。

## T2 打分给模型、加权给 Python
原因：个人/岗位二维打分是"判断"，交强模型；加权总分和阈值比较是"算术"，留 Python。
对比：若让模型直接算总分，结果不可复现、不可测试，被问"权重怎么调"无法
现场演示。拆开后 _weighted_total 是纯函数，改 WEIGHTS 重跑即可。
追问准备：能讲"为什么不让模型一步出总分"。

## T2 阈值定为 60，触发 human-in-the-loop 而非直接过滤
原因：加权总分 < 60 触发询问用户"是否继续准备这家"。
对比：直接过滤掉低分岗位会让 Agent 替用户悄悄丢机会；边缘匹配（如55分）
可能仍值得投。把决定权交还用户，这是 interrupt 分支存在的理由。
注：60 为初值，Day 10 用 Bad Case 校准。
追问准备：能讲"为什么 human-in-the-loop 而非自动过滤"。

## T2 gap 强制核对简历全文
原因：模型列 gap 时漏读简历"专业技能"段，把已具备能力误判为缺失
（实测把"熟练使用 Cursor/Claude Code"列成 high 缺口）。
对策：prompt 第四步加约束——列 gap 前逐条在简历全文检索是否已具备。
追问准备：这是一条真实 Bad Case，能讲"prompt 约束如何修复事实性错误"。

## human-in-the-loop 用 interrupt 而非直接过滤
决策：T2 低于阈值暂停问用户，不自动丢弃岗位。
实现：`human_check` 节点 + `agent/graph.py` 条件边 → END 或继续 T3/T4。

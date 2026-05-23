### 决策记录

# 为什么状态文件用 TypedDict 不用 MessageGraph ：
MessageGraph 的 state 是一串固定的消息列表（一条条信息依次往列表里追加），存不了 jd_structured、match_result 这种结构化中间结果。项目的 Agent 要在 state 里存四个工具的产物，必须自定义结构化字段，所以用 TypedDict。

# Plan-Execute vs ReAct :
Plan-Excute模式先规划好流程路线，再调用工具进行具体执行；ReAct模式按Thought-Action-Observation循环进行进行推进，观察每一步的结果决定下一步的行动。
两者各有优劣：Plan适合流程相对固定的任务如coding Agent，但如果某个环节失败不好调整（需要引入重规划），ReAct适合流程每步产出随机性高，比较灵活的任务，比如deepresearch Agent，但缺点是控制性弱，成本高
对于本项目，JD解析 匹配度分析 初步行动建议 面试包 四个环节在流程中位置明确，前后联系紧密，用Plan模式能够达到比较好的效果，ReAct模式的灵活性在这个场景中属于冗余特性，且成本更高，选取前者作为最终实现

## 为什么编排框架选型用LangGraph 而非 LangChain（chain抽象） ：
LangChain 的核心是 Chain——把"调LLM→解析→再调"打包成高层抽象，上手快、封装好，但流程结构是有向无环链，顺序由框架定，state 以消息列表为主，控制流藏在抽象里、透明度低。LangGraph 走相反路线：只提供节点、边、状态三个底层原语，流程怎么走、state 存什么、何时循环全由开发者显式编排。代价是编排逻辑要自己写、上手慢一些，收益是流程任意成图（含循环和条件分支）、状态可自定义、每段控制流都是看得懂讲得清的自己的代码。
选 LangGraph 的依据是本项目作为 Plan-Execute Agent 有三个结构性需求，LangChain 的链都满足不了。一是失败重规划：工具失败要回到 Executor 重走，这是循环回环，有向无环链做不了。二是结构化中间状态：state 要存 jd_structured、match_result 等四个工具的结构化产出，LangChain 以消息列表为主存不下。三是条件路由：匹配度低于阈值要触发 human-in-the-loop 分支，需要条件边。
LangGraph "自带功能轻"是有意的设计取舍——它提供机制而非策略，把控制权交还开发者；重的编排逻辑本属业务逻辑、不该由框架预设。但它并非纯裸写，真正省事的内置能力在 interrupt（human-in-the-loop）和 checkpointer（状态持久化/断点续跑），这两个自己实现成本很高。
为什么不用 LangChain 更快？LangChain落点在链做不了循环和结构化 state，这是两个结构性限制
一句话总结——LangChain 偏链式抽象、上手快但流程不透明；LangGraph 是图状态机，把节点/边/状态暴露给开发者显式编排，Agent 需要的循环与条件控制权正由此而来。

## 多模态直接抽取，不用 OCR
决策：JD截图直接喂 Qwen-VL，按schema结构化抽取，不走 OCR→拼接→纠错链路。
原因：
OCR 只输出纯文字串，不理解版式——标签、分栏、"哪段是职责/哪段是要求"它分不清，需自己写代码二次拼接和归类。
多模态模型同时处理版式 + 文字，能直接理解"这是技术栈标签区""这是任职要求列表"，一步到位。
JD 截图版式杂（电脑版/手机版、分栏、标签云），正是 OCR 的弱项、多模态的强项。
对比：OCR 链路 = 识别 + 拼接 + 归类三步且每步可能丢信息；多模态 = 一次调用。
追问准备：被问"多图顺序/信息冲突怎么处理"——多张截图一次性塞进同一次模型调用，模型自己理解合并，代码不做顺序假设、不做拼接；抽不到的字段靠 schema 的 Optional / 默认空 list 兜底。

## JD 库独立，不复用 RAG 项目的 MCP
决策：JD 分析 Agent 自建本地 Chroma 库，不通过 MCP 调 RAG 项目入库。
原因：
RAG 项目的能力是"切片 → 召回 → 重排 → 增强生成"，为问答场景设计。
JD 库的需求只有两点：整条存（不切片）+ 语义检索取回。用不上 RAG 的切片/召回/增强生成链路。
强行复用 = 把简单需求套进重链路，反而增加耦合和复杂度。
JD 库定位：长期记忆。每条 JD 整条存（含 raw_text），embedding 基于关键文本（岗位名+公司+技术栈+职责+加分项）支持语义搜索，后续按公司/语义取回完整分析结果。
对比：复用 RAG-MCP = 跨项目依赖 + 用不上的能力；独立 Chroma = 自给自足、接口可控。
追问准备：能讲清"RAG 和向量库不是一回事"——RAG 是一套检索增强生成的方法链，向量库只是其中的存取组件；本项目只需要后者。

## 模型分级：T1 用弱模型 Qwen-VL-Plus
决策：T1 抽取用 qwen-vl-plus（弱多模态），Planner + T2/T3/T4 用强模型。
原因：
T1 是"照着 schema 填空"的结构化抽取，不需要推理，弱模型足够。
plus 比 max 便宜，MVP 阶段够用；和 RAG 项目同平台（DashScope），同一 API key，省一次选型。
对比：全程强模型 = 成本高且 T1 用不上推理能力；分级 = 省成本，Day10 出"分级 vs 全强模型"成本对比数据。

## embedding 选 text-embedding-v3
决策：JD 库 embedding 用 DashScope text-embedding-v3。
原因：检索质量优于 v2，价格同档（约 ¥0.0005/千token）；与 Qwen 同平台同 key，不引入新依赖。
embed 文本范围：job_title + company + tech_stack + responsibilities + bonus。不含 raw_text——原文太长、噪音多，会稀释语义（搜"LangChain岗位"时被无关内容拉偏）。raw_text 整条存进 metadata，不参与 embedding。
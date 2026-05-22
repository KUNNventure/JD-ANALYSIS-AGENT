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
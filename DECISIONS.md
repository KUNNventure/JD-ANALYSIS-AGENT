
# 为什么状态文件用 TypedDict 不用 MessageGraph ：
MessageGraph 的 state 是一串固定的消息列表（一条条信息依次往列表里追加），存不了 jd_structured、match_result 这种结构化中间结果。项目的 Agent 要在 state 里存四个工具的产物，必须自定义结构化字段，所以用 TypedDict。

# Plan-Execuet vs ReAct :
Plan-Excute模式先规划好流程路线，再调用工具进行具体执行；ReAct模式按Thought-Action-Observation循环进行进行推进，观察每一步的结果决定下一步的行动。
两者各有优劣：Plan适合流程相对固定的任务如coding Agent，但如果某个环节失败不好调整（需要引入重规划），ReAct适合流程每步产出随机性高，比较灵活的任务，比如deepresearch Agent，但缺点是控制性弱，成本高
对于本项目，JD解析 匹配度分析 初步行动建议 面试包 四个环节在流程中位置明确，前后联系紧密，用Plan模式能够达到比较好的效果，ReAct模式的灵活性在这个场景中属于冗余特性，且成本更高，选取前者作为最终实现模式
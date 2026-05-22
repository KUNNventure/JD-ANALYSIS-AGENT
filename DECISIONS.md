为什么状态文件用 TypedDict 不用 MessageGraph：
MessageGraph 的 state 固定是一串消息列表，存不了 jd_structured、match_result 这种结构化中间结果。项目的 Agent 要在 state 里存四个工具的产物，必须自定义字段，所以用 TypedDict。
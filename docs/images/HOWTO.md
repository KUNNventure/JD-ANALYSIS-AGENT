# 终端演示截图（README 用）

目标文件：`docs/images/demo-terminal.png`（README 顶部引用）

## 推荐：截「可读摘要」而不是整屏 JSON

整屏 JSON 对 HR 不友好。用历史摘要命令，输出短、信息密度高：

```powershell
cd C:\Users\xsk\jd-analysis-agent
.\venv\Scripts\activate
python main.py history 1
```

确保终端里能看到至少：

- `加权总分` + 个人/岗位分
- 1～2 条 `gap`
- `招呼语` 开头一两句
- `面试包` 题数 + 第 1 道题标题

若还没有历史记录，先跑一遍全流程（需配置 `.env` 与 `resume.md`）：

```powershell
python main.py
```

跑完后再执行 `python main.py history 1`。

## Windows 截图步骤

1. 把终端窗口拉宽，字号调到 **14～16**（VS Code / Windows Terminal：设置 → 外观 → 字体大小）
2. 向上滚动，让 **从 `========== 匹配 (T2)` 到面试包前几行** 都在一屏内
3. **Win + Shift + S** → 矩形截图 → 框选终端内容区
4. 画图 / 粘贴后 **另存为** `demo-terminal.png` 到本目录
5. 打开 README，确认图片能显示；提交：

   ```powershell
   git add docs/images/demo-terminal.png README.md
   git commit -m "docs: add terminal demo screenshot"
   ```

## 可选：全流程跑通截图

若希望展示 Agent 执行过程，可截 `python main.py` 结束前的片段，包含：

- `▶ T1` / `✓ T1` 这类进度行
- 最后的 `======== 匹配分析 (T2) ========` 分数块

同一文件覆盖保存即可，README 只放一张主图。

## 隐私检查（提交前）

截图里不要出现：

- `DASHSCOPE_API_KEY` 或 `.env` 内容
- 真实手机号、邮箱、身份证号
- 未脱敏的公司内部信息

示例 JD 使用仓库内 `test_images/` 即可；简历用模板或已脱敏内容。

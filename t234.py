"""跳过 T1，用缓存的 jd_sample.json + resume.md 跑 T2→T3→T4。"""
from dotenv import load_dotenv
load_dotenv()

import json
import sys
import os

# 确保项目根目录在 path 里
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tools.jd_matcher import match_jd
from tools.job_advisor import generate_advice
from tools.interview_prep import generate_interview_pack

# ---------- 加载输入 ----------
with open("tests/jd_sample.json", "r", encoding="utf-8") as f:
    jd_structured = json.load(f)

with open("resume.md", "r", encoding="utf-8") as f:
    resume = f.read()

# ---------- T2 ----------
print("=" * 50)
print("▶ 跑 T2：简历-JD 匹配")
print("=" * 50)
match_result = match_jd(jd_structured, resume)
print(json.dumps(match_result, ensure_ascii=False, indent=2))

# ---------- T3 ----------
print("\n" + "=" * 50)
print("▶ 跑 T3：求职准备建议")
print("=" * 50)
suggestions = generate_advice(jd_structured, match_result, resume)
print(json.dumps(suggestions, ensure_ascii=False, indent=2))

# ---------- T4 ----------
print("\n" + "=" * 50)
print("▶ 跑 T4：模拟面试包")
print("=" * 50)
interview_pack = generate_interview_pack(jd_structured, match_result)
print(json.dumps(interview_pack, ensure_ascii=False, indent=2))

print("\n✅ T2→T3→T4 全部跑通")
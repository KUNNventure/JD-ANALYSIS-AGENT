import requests
requests.Session.trust_env = False  # requests 完全忽略环境里的代理设置

"""单独测 T2。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import json
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

from tools.jd_parser import parse_jd
from tools.jd_matcher import match_jd

# 跑 T1 拿真实 jd_structured
jd_structured = json.loads(Path("tests/jd_sample.json").read_text(encoding="utf-8"))
print("已缓存 jd_sample.json")
print("=== T1 缓存 ===")
print(json.dumps(jd_structured, ensure_ascii=False, indent=2))

# 跑 T2
resume = Path("resume.md").read_text(encoding="utf-8")
result = match_jd(jd_structured, resume)
print("=== T2 match_result ===")
print(json.dumps(result, ensure_ascii=False, indent=2))
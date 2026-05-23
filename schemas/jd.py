from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
import uuid


class CompanyInfo(BaseModel):
    """工商信息(用户截了工商页才有)"""
    registered_capital: Optional[str] = None   # 注册资本,如"5000万"
    established_date: Optional[str] = None     # 成立时间,如"2021-07-27"
    company_type: Optional[str] = None         # 企业类型,如"有限责任公司"


class JDStructured(BaseModel):
    """单条JD的结构化数据"""
    # 标识
    jd_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    # JD正文字段
    job_title: str = ""                         # 岗位名称
    company: str = ""                           # 公司名
    salary: Optional[str] = None                # 薪资
    location: Optional[str] = None              # 工作地点
    work_schedule: Optional[str] = None         # 到岗要求,如"3天/周 3个月"
    education: Optional[str] = None             # 学历要求
    tech_stack: list[str] = Field(default_factory=list)       # 技术栈标签
    responsibilities: list[str] = Field(default_factory=list) # 岗位职责
    requirements: list[str] = Field(default_factory=list)     # 任职要求
    bonus: list[str] = Field(default_factory=list)            # 加分项
    raw_text: str = ""                          # JD全文原文(T3必需)

    # 工商信息(可选)
    company_info: Optional[CompanyInfo] = None
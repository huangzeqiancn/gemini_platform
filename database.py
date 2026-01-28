import os
import datetime
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship, sessionmaker, declarative_base

# 确保数据目录存在
os.makedirs("./data", exist_ok=True)

Base = declarative_base()

class ApiConfig(Base):
    """API 配置池：管理不同的中转站或官方 Key"""
    __tablename__ = "api_configs"
    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False) 
    base_url = Column(String(255), nullable=False)
    api_key = Column(String(255), nullable=False)
    # 新增：适配 HMAC 接口需要的 User ID
    api_user = Column(String(100), nullable=True) 
    created_at = Column(DateTime, default=datetime.datetime.now)

class ResponseTemplate(Base):
    """新增：响应解析模板，用于动态抽取 JSON 中的字段"""
    __tablename__ = "response_templates"
    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False)  # 模板名称，如 "OpenAI标准"、"HMAC自定义"
    # 存储解析规则，例如：{"answer": "answer.0.value", "tokens": "cost_info.total_tokens"}
    mapping_rules = Column(Text, nullable=False) 
    raw_sample = Column(Text, nullable=True)   # 存储一份原始 JSON 样本供参考
    created_at = Column(DateTime, default=datetime.datetime.now)

class ScrapeTask(Base):
    """任务主表：记录一次抓取批次"""
    __tablename__ = "scrape_tasks"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    
    # --- 平台适配扩展 ---
    # 平台类型标识：'official' (官方SDK), 'api_openai' (OpenAI格式接口), 'api_hmac' (私有HMAC接口)
    platform_type = Column(String(50), default="official") 
    
    # 关联具体的 API 配置
    api_config_id = Column(Integer, ForeignKey("api_configs.id"), nullable=True)
    # 关联具体的解析模板
    template_id = Column(Integer, ForeignKey("response_templates.id"), nullable=True)
    
    model = Column(String(50))           # 使用的模型名称
    thinking_level = Column(String(20))   # 思考等级
    status = Column(String(20), default="pending") 
    created_at = Column(DateTime, default=datetime.datetime.now)
    
    # 建立关联
    entries = relationship("TaskEntry", backref="task", cascade="all, delete-orphan")
    api_config = relationship("ApiConfig")
    template = relationship("ResponseTemplate")

class TaskEntry(Base):
    """结果详情表：存储每一个具体的 Prompt 及其对应的返回结果"""
    __tablename__ = "task_entries"
    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey("scrape_tasks.id"))
    prompt = Column(Text, nullable=False)
    answer = Column(Text)          # 解析后的纯文本答案
    raw_response = Column(Text)    # 原始完整 JSON 字符串（非常重要，用于后期重新解析）
    tokens_used = Column(Integer, default=0)
    status = Column(String(20))    # success, failed
    created_at = Column(DateTime, default=datetime.datetime.now)

class TaskPreset(Base):
    """任务预设：存储 System Prompt 模板"""
    __tablename__ = "task_presets"
    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False) 
    content = Column(Text, nullable=False)    
    created_at = Column(DateTime, default=datetime.datetime.now)

# --- 数据库连接配置 ---
DB_URL = "sqlite:///./data/gemini_platform.db"
engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """初始化数据库表结构"""
    Base.metadata.create_all(bind=engine)
    print("✅ 数据库表结构更新成功！")
import os
import datetime
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship, sessionmaker, declarative_base

# 确保目录存在
os.makedirs("./data", exist_ok=True)

Base = declarative_base()

class ApiConfig(Base):
    """API 密钥池：管理不同的中转站或官方 Key"""
    __tablename__ = "api_configs"
    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False) 
    base_url = Column(String(255), nullable=False)
    api_key = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.now)

class ScrapeTask(Base):
    """任务主表：记录一次抓取批次（如：'2024人大提问集'）"""
    __tablename__ = "scrape_tasks"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    model = Column(String(50))           # 使用的模型枚举值
    thinking_level = Column(String(20))   # 思考等级枚举值
    status = Column(String(20), default="pending") # pending, running, completed
    created_at = Column(DateTime, default=datetime.datetime.now)
    
    # 建立与 TaskEntry 的一对多关联
    entries = relationship("TaskEntry", backref="task", cascade="all, delete-orphan")

class TaskEntry(Base):
    """结果详情表：存储每一个具体的 Prompt 及其对应的返回结果"""
    __tablename__ = "task_entries"
    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey("scrape_tasks.id"))
    prompt = Column(Text, nullable=False)
    answer = Column(Text)          # 解析后的纯文本答案
    raw_response = Column(Text)    # 原始完整 JSON 字符串
    tokens_used = Column(Integer, default=0)
    status = Column(String(20))    # success, failed
    created_at = Column(DateTime, default=datetime.datetime.now)

# 在 database.py 中添加这个类
class TaskPreset(Base):
    """任务预设：存储 System Prompt 模板"""
    __tablename__ = "task_presets"
    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False) # 预设名称，如“实时环境注入”
    content = Column(Text, nullable=False)    # 具体的 System Message 内容
    created_at = Column(DateTime, default=datetime.datetime.now)

# 记得在 main.py 或测试脚本里执行 Base.metadata.create_all(bind=engine)

# 配置 SQLite 数据库
DB_URL = "sqlite:///./data/gemini_platform.db"
engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """初始化数据库表结构"""
    Base.metadata.create_all(bind=engine)
    print("✅ 数据库表结构初始化成功！")
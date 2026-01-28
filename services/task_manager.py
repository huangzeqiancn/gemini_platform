# services/task_manager.py
import sys
import os
import logging
import asyncio
import json
import uuid
import hmac
import hashlib
import base64
import datetime
import requests
from sqlalchemy.orm import Session
import database as db
from database import SessionLocal

# 确保能找到根目录下的 parser_utils
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from parser_utils import extract_standard_data # 完美利用你的新文件
# 在 task_manager.py 顶部添加
from auth_utils import get_hmac_auth
from services.scraper import run_single_scrape

def start_batch_task(task_id: int, api_id: int, prompts: list, system_instruction: str, thinking: str = "minimal"):
    """
    后台批量处理逻辑 - 完整修复版
    1. 增加了 thinking 参数接收，防止参数个数不匹配崩溃
    2. 增强了 task 对象的健壮性
    """
    s = SessionLocal()
    task = None  # 提前声明，防止 finally 块报错
    
    try:
        # 1. 获取任务
        task = s.query(db.ScrapeTask).filter(db.ScrapeTask.id == task_id).first()
        if not task:
            print(f"❌ 错误：找不到任务 ID {task_id}")
            return

        # 2. 补全 task 对象的 thinking_level (以防万一)
        # 如果数据库里的值为 None，将传进来的 thinking 值补给它
        if not task.thinking_level:
            task.thinking_level = thinking

        # 3. 获取关联配置 (利用 SQLAlchemy relationship)
        config = task.api_config
        template = task.template

        if not config:
            print(f"❌ 错误：任务 {task_id} 未关联有效的 API 配置")
            task.status = "failed"
            s.commit()
            return

        # 4. 更新任务为运行中
        task.status = "running"
        # 提示：如果你希望由前端控制是否开启搜索，请不要在这里写死 True
        task.use_google_search = True 
        s.commit()

        # 5. 循环执行抓取
        for p_text in prompts:
            # 调用 scraper.py 里的函数
            # 注意：这里的 task 对象在当前 Session(s) 中是活的
            success = run_single_scrape(
                task=task, 
                api_config=config, 
                prompt=p_text, 
                system_instruction=system_instruction
            )
            print(f"📊 Prompt: {p_text[:20]}... | 执行结果: {'✅ 成功' if success else '❌ 失败'}")

        # 6. 任务正常结束
        task.status = "completed"
        s.commit()

    except Exception as e:
        print(f"🚨 任务主循环崩溃: {str(e)}")
        if s and task:
            try:
                task.status = "failed"
                s.commit()
            except:
                pass
    finally:
        if s:
            s.close()
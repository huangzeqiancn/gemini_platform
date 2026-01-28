import json
import datetime
from enum import Enum
from openai import OpenAI
from database import SessionLocal, TaskEntry, ScrapeTask

# --- 枚举定义 ---
class GeminiModel(Enum):
    PRO = "gemini-3-pro-preview"
    FLASH = "gemini-3-flash-preview"

class ThinkingLevel(Enum):
    MINIMAL = "minimal"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

# --- 核心逻辑 ---

def apply_template(content: str):
    """将模板中的 {{变量}} 替换为真实数据"""
    now = datetime.datetime.now()
    # 注入当前时间信息
    replacements = {
        "{{current_time}}": now.strftime("%Y-%m-%d %H:%M:%S"),
        "{{day_of_week}}": now.strftime("%A"),
        "{{location}}": "Washington, DC"
    }
    for placeholder, value in replacements.items():
        content = content.replace(placeholder, value)
    return content

def run_single_scrape(api_config, task_id, prompt, model_name, thinking_level, system_template=None):
    """
    执行单条抓取、处理数据并安全存入数据库
    api_config: 数据库中的 ApiConfig 对象（包含 api_key 和 base_url）
    """
    client = OpenAI(api_key=api_config.api_key, base_url=api_config.base_url)
    db = SessionLocal()
    
# 1. 处理动态变量替换
    now = datetime.datetime.now()
    if system_template:
        system_content = system_template.replace("{{current_time}}", now.strftime('%Y-%m-%d %H:%M:%S'))
        system_content = system_content.replace("{{day_of_week}}", now.strftime('%A'))
    else:
        # 默认回退方案
        system_content = f"You are Gemini. Current time: {now.strftime('%Y-%m-%d %H:%M:%S')}"

    try:
        # 1. 调用接口
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": prompt}
            ],
            extra_body={
                "generationConfig": {
                    "thinkingConfig": {"thinkingLevel": thinking_level}
                }
            }
        )

        # 2. 提取原始数据 (OpenAI 兼容格式)
        raw_res = response.model_dump()
        answer = raw_res['choices'][0]['message']['content']
        tokens = raw_res.get('usage', {}).get('total_tokens', 0)

        # 3. 核心：安全存入数据库 (整合了 save_entry_to_db 的逻辑)
        entry = TaskEntry(
            task_id=task_id,
            prompt=str(prompt).strip(), # 确保字符串类型并清理首尾空格
            answer=answer,
            # 使用 ensure_ascii=False 确保中文和特殊符号不被破坏
            raw_response=json.dumps(raw_res, ensure_ascii=False),
            tokens_used=tokens,
            status="success"
        )
        db.add(entry)
        db.commit()
        return True

    except Exception as e:
        # 记录失败状态，保存错误信息
        error_info = {"error": str(e)}
        entry = TaskEntry(
            task_id=task_id,
            prompt=str(prompt).strip(),
            answer=f"抓取失败: {str(e)}",
            raw_response=json.dumps(error_info, ensure_ascii=False),
            status="failed",
            tokens_used=0
        )
        db.add(entry)
        db.commit()
        print(f"❌ 抓取任务失败: {e}")
        return False
    finally:
        db.close()
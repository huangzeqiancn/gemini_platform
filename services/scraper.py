import json
import datetime
import requests
import uuid
import sys
import os
import time
from enum import Enum
from database import SessionLocal, TaskEntry

# 导入工具类
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from auth_utils import get_hmac_auth
from parser_utils import get_value_by_path

class GeminiModel(Enum):
    PRO = "gemini-3-pro-preview"
    FLASH = "gemini-3-flash-preview"

class ThinkingLevel(Enum):
    MINIMAL = "minimal"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

def apply_template(content: str):
    """处理动态变量替换，增加更多上下文"""
    if not content: return ""
    now = datetime.datetime.now()
    replacements = {
        "{{current_time}}": now.strftime("%Y-%m-%d %H:%M:%S"),
        "{{day_of_week}}": now.strftime("%A"),
        "{{location}}": "Washington, DC, United States",
    }
    for placeholder, value in replacements.items():
        content = content.replace(placeholder, value)
    return content

def make_api_request(url, headers, payload, max_retries=3, base_timeout=180):
    """
    执行API请求，带重试和递增超时机制
    """
    for attempt in range(max_retries):
        try:
            # 递增超时时间
            timeout = base_timeout + (attempt * 60)
            print(f"🔄 尝试 {attempt + 1}/{max_retries}，超时设置: {timeout}秒")
            
            resp = requests.post(
                url, 
                headers=headers, 
                json=payload, 
                timeout=timeout
            )
            
            if resp.status_code != 200:
                error_msg = f"HTTP {resp.status_code}: {resp.text[:500]}"
                print(f"❌ {error_msg}")
                if 400 <= resp.status_code < 500:
                    raise Exception(error_msg)
                
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    print(f"⏳ 等待 {wait_time}秒 后重试...")
                    time.sleep(wait_time)
                    continue
                else:
                    raise Exception(error_msg)
            
            return resp.json()
            
        except requests.exceptions.Timeout:
            print(f"⏱️ 请求超时 (第{attempt + 1}次尝试)")
            if attempt < max_retries - 1:
                time.sleep(5)
            else:
                raise Exception("请求超时，建议降低thinking_level或暂时关闭搜索工具")
        except Exception as e:
            raise e
    raise Exception("未知错误：请求未能完成")

def run_single_scrape(task, api_config, prompt, system_instruction):
    """
    完整修复版：解决 NameError 并优化 Pro 模型配置
    """
    db = SessionLocal()

    # --- 【关键修复 1】：前置定义所有变量，确保任何路径下 print/except 都能访问 ---
    thinking_level = "minimal"
    use_search = False
    tokens = 0
    status = "failed"
    system_content = ""

    try:
        # 1. 变量初始化（安全提取）
        thinking_level = getattr(task, 'thinking_level', 'minimal') or 'minimal'
        use_search = getattr(task, 'use_google_search', False)
        
        # 2. 指令预处理
        if system_instruction:
            system_content = apply_template(system_instruction)
        else:
            system_content = f"You are Gemini. Current time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        # 3. 构造配置项
        # 针对 Gemini 3 Pro: 由于其思维链(Reasoning)极长，必须调大输出上限，否则会返回空
        is_pro = "pro" in task.model.lower()
        max_tokens = 8192 if is_pro else 2048
        
        generation_config = {
            "max_output_tokens": max_tokens,
            "temperature": 1.0,
            "thinkingConfig": {"thinkingLevel": thinking_level}
        }

        # Google Search工具配置
        tools = [{"google_search": {}}] if use_search else None

        # 4. 准备请求头和负载
        if task.platform_type == "api_hmac":
            # --- 模式 A: 私有 HMAC 协议 ---
            auth_header, dt = get_hmac_auth(api_config.api_key, api_config.api_user)
            headers = {
                'Authorization': auth_header,
                'Date': dt,
                'Source': 'test_api',
                'Apiversion': 'v2.03',
                'Content-Type': 'application/json'
            }
            #full_prompt = f"{system_content}\n\nUser Query: {prompt}"
            # 注意：由于私有网关过滤 role:system，必须将指令强制拼接入 user.value
            combined_value = f"SYSTEM_INSTRUCTION:\n{system_content}\n\nUSER_QUERY:\n{prompt}"
            payload = {
                "request_id": str(uuid.uuid4()),
                "model_marker": task.model,
                "messages": [
                    {"role": "system", "content": [{"type": "text", "value": system_content}]},
                    #{"role": "user", "content": [{"type": "text", "value": prompt}]}
                    {"role": "user", "content": [{"type": "text", "value": combined_value}]}
                ],
                "generation_config": generation_config, # HMAC 模式使用下划线
            }
            print(f"📝 请求头: {combined_value}")
            if tools:
                payload["tools"] = tools
        else:
            # --- 模式 B: 标准协议 ---
            headers = {
                "Authorization": f"Bearer {api_config.api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": task.model,
                "messages": [
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": prompt}
                ],
                "generationConfig": generation_config, # 标准模式使用驼峰
            }
            if tools:
                payload["tools"] = tools

        # 5. 执行请求
        print(f"📤 发送请求到: {api_config.base_url}")
        # 【关键修复 2】：这里直接使用前面统一定义的变量，不再访问 task.thinking_level
        print(f"📝 模型: {task.model}, 思考等级: {thinking_level}, 搜索: {use_search}")
        print(f"📝 系统指令: {system_content}")
        
        raw_res = make_api_request(
            api_config.base_url, 
            headers, 
            payload,
            max_retries=3,
            base_timeout=180
        )

        # 6. 解析结果
        mapping_rules = {"answer": "choices.0.message.content", "tokens": "usage.total_tokens"}
        if task.template and task.template.mapping_rules:
            try:
                mapping_rules = json.loads(task.template.mapping_rules)
            except: pass

        answer = get_value_by_path(raw_res, mapping_rules.get("answer", ""))
        tokens = get_value_by_path(raw_res, mapping_rules.get("tokens", "")) or 0
        
        # 处理空返回逻辑
        if not answer or str(answer).strip() == "":
            finish_reason = get_value_by_path(raw_res, "choices.0.finish_reason")
            error_msg = get_value_by_path(raw_res, "error.message")
            if error_msg:
                answer = f"⚠️ API错误: {error_msg}"
            else:
                answer = f"⚠️ 无内容。状态: {finish_reason}。建议检查 max_output_tokens 设置。"
            status = "failed"
        else:
            # 检查是否有联网证据
            grounding = get_value_by_path(raw_res, "choices.0.message.tool_calls")
            if grounding:
                answer += "\n\n[注：该回答使用了外部工具查询]"
            status = "success"

        # 7. 数据入库
        entry = TaskEntry(
            task_id=task.id,
            prompt=prompt,
            answer=str(answer),
            raw_response=json.dumps(raw_res, ensure_ascii=False),
            tokens_used=int(tokens),
            status=status
        )
        db.add(entry)
        db.commit()
        print(f"✅ 抓取成功，Tokens: {tokens}")
        return True

    except Exception as e:
        if db: db.rollback()
        error_detail = str(e)
        print(f"❌ 抓取失败: {error_detail}")
        
        # 记录失败信息（此时变量已安全定义）
        entry = TaskEntry(
            task_id=task.id,
            prompt=prompt,
            answer=f"抓取异常: {error_detail}",
            raw_response=json.dumps({"error": error_detail, "last_level": thinking_level}, ensure_ascii=False),
            status="failed",
            tokens_used=0
        )
        if db:
            db.add(entry)
            db.commit()
        return False
    finally:
        if db: db.close()
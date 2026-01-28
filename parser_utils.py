# parser_utils.py
import json

def get_value_by_path(data, path):
    """
    核心解析引擎：支持点号路径抽取
    支持格式：'choices.0.message.content' 或 'answer.0.value'
    """
    if not path or data is None:
        return None
    
    try:
        keys = path.split('.')
        current = data
        for key in keys:
            if isinstance(current, list):
                # 如果当前是列表，key 应该是索引数字
                current = current[int(key)]
            elif isinstance(current, dict):
                # 如果当前是字典，正常取值
                current = current.get(key)
            else:
                return None
        return current
    except (IndexError, KeyError, ValueError, TypeError) as e:
        # 这里可以记录日志，方便在调试中心查错
        print(f"解析路径 [{path}] 出错: {e}")
        return None

def extract_standard_data(raw_response, mapping_rules=None):
    """
    根据映射规则提取标准字段
    mapping_rules 示例: {"answer": "answer.0.value", "tokens": "cost_info.total_tokens"}
    如果 mapping_rules 为空，默认按标准 OpenAI 格式解析
    """
    # 如果没传规则，默认回退到 OpenAI/Gemini 标准格式
    if mapping_rules is None:
        mapping_rules = {
            "answer": "choices.0.message.content", 
            "tokens": "usage.total_tokens"
        }
    # 如果传的是字符串 JSON，转为字典
    if isinstance(mapping_rules, str):
        try:
            mapping_rules = json.loads(mapping_rules)
        except:
            mapping_rules = {"answer": "choices.0.message.content", "tokens": "usage.total_tokens"}
    
    answer = get_value_by_path(raw_response, mapping_rules.get("answer", ""))
    tokens = get_value_by_path(raw_response, mapping_rules.get("tokens", ""))
    
    # 强制转换 tokens 为整数，如果解析失败默认为 0
    try:
        tokens = int(tokens) if tokens is not None else 0
    except:
        tokens = 0
        
    return {
        "answer": str(answer) if answer is not None else "解析失败：未找到内容",
        "tokens": tokens
    }
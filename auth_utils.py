import hmac
import hashlib
import time
import json
import base64
import datetime

def generate_hmac_headers(api_key, api_user, payload):
    """
    通用型 HMAC-SHA256 签名 (适用于大多数现代标准)
    """
    timestamp = str(int(time.time()))
    body_str = json.dumps(payload, separators=(',', ':'))
    sign_str = f"{timestamp}{api_user}{body_str}"
    
    signature = hmac.new(
        api_key.encode('utf-8'),
        sign_str.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    return {
        "X-Timestamp": timestamp,
        "X-User": api_user,
        "X-Signature": signature
    }

def get_hmac_auth(api_key, api_user):
    """
    专为你提到的 v2.03 私有协议设计的签名逻辑 (SHA1)
    """
    # 必须使用 datetime 模块
    dt = datetime.datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')
    sign_str = f"date: {dt}\nsource: test_api"
    
    # 按照你之前的逻辑使用 sha1
    sign = hmac.new(api_key.encode(), sign_str.encode(), hashlib.sha1).digest()
    
    # 必须使用 base64 模块
    signature_b64 = base64.b64encode(sign).decode()
    
    auth_header = f'hmac id="{api_user}", algorithm="hmac-sha1", headers="date source", signature="{signature_b64}"'
    return auth_header, dt
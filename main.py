import pandas as pd
import datetime
import time
import json
import uuid
import hmac
import hashlib
import base64
import requests
import os
from io import BytesIO
from fastapi import FastAPI, Request, Form, Depends, Body, HTTPException, BackgroundTasks
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, StreamingResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

import database as db
from services.scraper import run_single_scrape, GeminiModel, ThinkingLevel
from services.task_manager import start_batch_task
from database import engine, Base
from parser_utils import get_value_by_path # 引用你刚创建的文件
from auth_utils import get_hmac_auth  # 确保已经导入你之前写的工具函数

# 初始化数据库表结构
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Gemini 抓取任务管理平台 (完整增强版)")

# 配置模板目录
templates = Jinja2Templates(directory="templates")

# --- 数据库依赖项 ---
def get_db():
    session = db.SessionLocal()
    try:
        yield session
    finally:
        session.close()

# --- 1. 数据管理中心 ---
@app.get("/data_center")
def data_center(request: Request, search: str = "", task_id: int = 0, s: Session = Depends(get_db)):
    query = s.query(db.TaskEntry).join(db.ScrapeTask)
    if search:
        query = query.filter((db.TaskEntry.prompt.contains(search)) | (db.TaskEntry.answer.contains(search)))
    if task_id > 0:
        query = query.filter(db.TaskEntry.task_id == task_id)
    
    entries = query.order_by(db.TaskEntry.created_at.desc()).all()
    tasks = s.query(db.ScrapeTask).all()

    # 计算统计数据
    total_tokens = sum(e.tokens_used for e in entries if e.tokens_used)
    avg_tokens = round(total_tokens / len(entries), 1) if entries else 0

    return templates.TemplateResponse("data_center.html", {
        "request": request,
        "entries": entries,
        "tasks": tasks,
        "search": search,
        "current_task_id": task_id,
        "stats": {
            "total_count": len(entries),
            "total_tokens": total_tokens,
            "avg_tokens": avg_tokens
        }
    })

# --- 2. Excel 导出接口 ---
@app.get("/data/export")
def export_data(task_id: int = 0, search: str = "", s: Session = Depends(get_db)):
    try:
        query = s.query(db.TaskEntry).join(db.ScrapeTask)
        if task_id > 0:
            query = query.filter(db.TaskEntry.task_id == task_id)
        if search:
            query = query.filter((db.TaskEntry.prompt.contains(search)) | (db.TaskEntry.answer.contains(search)))
        
        entries = query.all()
        if not entries:
            return JSONResponse(status_code=400, content={"message": "无匹配数据可导出"})

        data_list = []
        for e in entries:
            data_list.append({
                "任务名称": e.task.name if e.task else "未归类",
                "Prompt": e.prompt,
                "AI结果": e.answer,
                "Tokens": e.tokens_used,
                "抓取时间": e.created_at.strftime("%Y-%m-%d %H:%M") if e.created_at else ""
            })
        
        df = pd.DataFrame(data_list)
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='数据报表')
        
        output.seek(0)
        curr_time = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"export_{curr_time}.xlsx"
        
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        print(f"Export Error: {str(e)}")
        return JSONResponse(status_code=500, content={"detail": str(e)})

# --- 3. 批量删除 ---
@app.post("/data/batch_delete")
def batch_delete(entry_ids: list[int] = Body(...), s: Session = Depends(get_db)):
    try:
        s.query(db.TaskEntry).filter(db.TaskEntry.id.in_(entry_ids)).delete(synchronize_session=False)
        s.commit()
        return {"status": "success", "message": f"成功删除 {len(entry_ids)} 条记录"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"message": str(e)})

# --- 4. 首页 (任务列表) ---
@app.get("/")
def index(request: Request, s: Session = Depends(get_db)):
    tasks = s.query(db.ScrapeTask).order_by(db.ScrapeTask.created_at.desc()).all()
    api_configs = s.query(db.ApiConfig).all()
    presets = s.query(db.TaskPreset).all() 
    templates_list = s.query(db.ResponseTemplate).all() # 新增：解析模板
    
    return templates.TemplateResponse("index.html", {
        "request": request, 
        "tasks": tasks, 
        "apis": api_configs,
        "presets": presets,
        "templates": templates_list,
        "models": [m.value for m in GeminiModel],
        "thinking_levels": [t.value for t in ThinkingLevel]
    })

# --- 5. API 配置管理 (含探测功能) ---
@app.get("/api_config")
def api_config_page(request: Request, s: Session = Depends(get_db)):
    configs = s.query(db.ApiConfig).all()
    presets = s.query(db.TaskPreset).all()
    templates_list = s.query(db.ResponseTemplate).all()
    return templates.TemplateResponse("api_config.html", {
        "request": request, 
        "configs": configs, 
        "presets": presets,
        "templates": templates_list
    })

@app.post("/api_config/add")
def add_api_config(
    name: str = Form(...), 
    base_url: str = Form(...), 
    api_key: str = Form(...), 
    api_user: str = Form(None), # HMAC 接口需要
    s: Session = Depends(get_db)
):
    # 处理可能的空字符串，统一存储逻辑
    processed_user = api_user.strip() if api_user and api_user.strip() else None
    
    new_cfg = db.ApiConfig(
        name=name, 
        base_url=base_url, 
        api_key=api_key, 
        api_user=processed_user
    )
    s.add(new_cfg)
    s.commit()
    return RedirectResponse(url="/api_config", status_code=303)

@app.get("/api_config/get/{cfg_id}")
def get_api_config(cfg_id: int, s: Session = Depends(get_db)):
    cfg = s.query(db.ApiConfig).filter(db.ApiConfig.id == cfg_id).first()
    if not cfg: return JSONResponse(status_code=404, content={"message": "Not found"})
    return {"id": cfg.id, "name": cfg.name, "base_url": cfg.base_url, "api_key": cfg.api_key, "api_user": cfg.api_user}

@app.post("/api_config/update")
def update_api_config(
    cfg_id: int = Form(...), 
    name: str = Form(...), 
    base_url: str = Form(...), 
    api_key: str = Form(...), 
    api_user: str = Form(None),
    s: Session = Depends(get_db)
):
    cfg = s.query(db.ApiConfig).filter(db.ApiConfig.id == cfg_id).first()
    if cfg:
        cfg.name, cfg.base_url, cfg.api_key, cfg.api_user = name, base_url, api_key, api_user
        s.commit()
    return RedirectResponse(url="/api_config", status_code=303)

@app.post("/api_config/delete/{cfg_id}")
def delete_api_config(cfg_id: int, s: Session = Depends(get_db)):
    cfg = s.query(db.ApiConfig).filter(db.ApiConfig.id == cfg_id).first()
    if cfg:
        s.delete(cfg)
        s.commit()
    return RedirectResponse(url="/api_config", status_code=303)

@app.post("/api_config/test")
async def test_api_connection(
    base_url: str = Body(..., embed=True),
    api_key: str = Body(..., embed=True),
    api_user: str = Body(None, embed=True),
    platform_type: str = Body(..., embed=True),
    model: str = Body("api_google_gemini-3-pro-preview", embed=True)
):
    """
    测试 API 连接并返回原始 JSON
    开发者可以在这里看到完整的接口返回结构，从而准确配置解析模板 (Schema)
    """
    try:
        test_prompt = "Hello, response with one word."
        
        if platform_type == "api_hmac":
            # --- 使用 auth_utils 中的统一签名逻辑 ---
            auth_header, dt = get_hmac_auth(api_key, api_user)
            
            headers = {
                'Authorization': auth_header,
                'Date': dt,
                'Source': 'test_api',
                'Apiversion': 'v2.03',
                'Content-Type': 'application/json'
            }
            # 私有协议特定的 Payload 结构
            payload = {
                "request_id": f"test_{int(time.time())}",
                "model_marker": model, # 使用动态传入的模型名
                #"model_marker": "api_google_gemini-3-pro-preview",
                "messages": [
                    {
                        "role": "user", 
                        "content": [{"type": "text", "value": test_prompt}]
                    }
                ]
            }
        else:
            # --- 标准 OpenAI / Gemini 协议 ---
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            # 探测时使用一个通用的模型名，若失败可让用户在前端手动修改
            payload = {
                "model": model, # 使用动态传入的模型名
                "messages": [{"role": "user", "content": test_prompt}]
            }
        
        # 执行请求，设置 15 秒超时防止卡死
        resp = requests.post(base_url, headers=headers, json=payload, timeout=15)
        
        # 尝试解析 JSON
        try:
            return resp.json()
        except Exception:
            # 如果不是 JSON 格式（如 502 错误返回的 HTML），返回原始文本
            return {"error": "接口未返回有效 JSON", "raw_text": resp.text[:500]}

    except Exception as e:
        return {"error": f"请求执行失败: {str(e)}"}

# --- 6. 预设管理 ---
@app.post("/presets/add")
def add_preset(name: str = Form(...), content: str = Form(...), s: Session = Depends(get_db)):
    new_pre = db.TaskPreset(name=name, content=content)
    s.add(new_pre)
    s.commit()
    return RedirectResponse(url="/api_config#preset-pane", status_code=303)

@app.get("/presets/get/{pre_id}")
def get_preset(pre_id: int, s: Session = Depends(get_db)):
    pre = s.query(db.TaskPreset).filter(db.TaskPreset.id == pre_id).first()
    if not pre: return JSONResponse(status_code=404, content={"message": "预设不存在"})
    return {"id": pre.id, "name": pre.name, "content": pre.content}

@app.post("/presets/update")
def update_preset(pre_id: int = Form(...), name: str = Form(...), content: str = Form(...), s: Session = Depends(get_db)):
    pre = s.query(db.TaskPreset).filter(db.TaskPreset.id == pre_id).first()
    if pre:
        pre.name, pre.content = name, content
        s.commit()
    return RedirectResponse(url="/api_config#preset-pane", status_code=303)

@app.post("/presets/delete/{pre_id}")
def delete_preset(pre_id: int, s: Session = Depends(get_db)):
    pre = s.query(db.TaskPreset).filter(db.TaskPreset.id == pre_id).first()
    if pre:
        s.delete(pre)
        s.commit()
    return RedirectResponse(url="/api_config#preset-pane", status_code=303)

# --- 7. 解析模板管理 ---
@app.post("/templates/add")
def add_response_template(name: str = Form(...), mapping_rules: str = Form(...), s: Session = Depends(get_db)):
    new_temp = db.ResponseTemplate(name=name, mapping_rules=mapping_rules)
    s.add(new_temp)
    s.commit()
    return RedirectResponse(url="/api_config#template-pane", status_code=303)

# --- 8. 任务执行与结果浏览 ---
@app.post("/tasks/create")
async def create_scrape_task(
    background_tasks: BackgroundTasks,
    task_name: str = Form(...),
    api_id: int = Form(...),
    platform_type: str = Form(...),
    template_id: int = Form(None),
    model: str = Form(...),
    thinking: str = Form(...),
    prompts_text: str = Form(...),
    preset_id: int = Form(...),
    s: Session = Depends(get_db)
):
    prompt_list = [p.strip() for p in prompts_text.split('\n') if p.strip()]
    preset = s.query(db.TaskPreset).filter(db.TaskPreset.id == preset_id).first()
    system_instruction = preset.content if preset else ""

    new_task = db.ScrapeTask(
        name=task_name, model=model, platform_type=platform_type,
        api_config_id=api_id, template_id=template_id,
        thinking_level=thinking, status="pending"
    )
    s.add(new_task)
    s.commit()

    background_tasks.add_task(
        start_batch_task, new_task.id, api_id, prompt_list, system_instruction, thinking
    )
    return RedirectResponse(url="/", status_code=303)

@app.get("/results/{task_id}")
def view_results(task_id: int, request: Request, s: Session = Depends(get_db)):
    task = s.query(db.ScrapeTask).filter(db.ScrapeTask.id == task_id).first()
    if not task: raise HTTPException(status_code=404, detail="任务不存在")
    return templates.TemplateResponse("results.html", {"request": request, "task": task})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
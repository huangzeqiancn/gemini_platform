import pandas as pd
import datetime  # 必须这样导入，才能支持 datetime.datetime.now()
from io import BytesIO
from fastapi import FastAPI, Request, Form, Depends, Body, HTTPException, BackgroundTasks
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import func # 用于统计 Tokens
import database as db
from services.scraper import GeminiModel, ThinkingLevel
from services.task_manager import start_batch_task
from database import engine, Base
from fastapi.responses import StreamingResponse, JSONResponse

# 在 FastAPI 应用初始化前或启动事件中添加
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Gemini 抓取任务管理平台")

# 配置模板目录
templates = Jinja2Templates(directory="templates")

# 数据库依赖项
def get_db():
    session = db.SessionLocal()
    try:
        yield session
    finally:
        session.close()

# --- 数据管理中心 ---
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
    
# --- Excel 导出接口 ---
@app.get("/data/export")
def export_data(
    task_id: int = 0, 
    search: str = "",  # 新增 search 参数接收
    s: Session = Depends(get_db)
):
    try:
        query = s.query(db.TaskEntry).join(db.ScrapeTask)
        # 2. 这里的逻辑必须和 data_center 页面完全一致
        if task_id > 0:
            query = query.filter(db.TaskEntry.task_id == task_id)
            
        if search:
            query = query.filter(
                (db.TaskEntry.prompt.contains(search)) | 
                (db.TaskEntry.answer.contains(search))
            )
        
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
        
        # 导出 Excel
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='数据报表')
        
        output.seek(0)
        
        # 修复报错的那一行：确保格式化正确
        curr_time = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"export_{curr_time}.xlsx"
        
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        # 如果还有报错，会在控制台打印具体原因
        print(f"Export Error: {str(e)}")
        return JSONResponse(status_code=500, content={"detail": str(e)})

@app.post("/data/batch_delete")
def batch_delete(entry_ids: list[int] = Body(...), s: Session = Depends(get_db)):
    try:
        s.query(db.TaskEntry).filter(db.TaskEntry.id.in_(entry_ids)).delete(synchronize_session=False)
        s.commit()
        return {"status": "success", "message": f"成功删除 {len(entry_ids)} 条记录"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"message": str(e)})

# --- 路由 1: 首页 (任务列表) ---
@app.get("/")
def index(request: Request, s: Session = Depends(get_db)):
    tasks = s.query(db.ScrapeTask).order_by(db.ScrapeTask.created_at.desc()).all()
    api_configs = s.query(db.ApiConfig).all()
    # 务必加上这一行
    presets = s.query(db.TaskPreset).all() 
    
    return templates.TemplateResponse("index.html", {
        "request": request, 
        "tasks": tasks, 
        "apis": api_configs,
        "presets": presets, # 传给前端
        "models": [m.value for m in GeminiModel],
        "thinking_levels": [t.value for t in ThinkingLevel]
    })

# --- 路由 2: API 配置管理页 ---
# --- API 配置管理 (增删改) ---
@app.get("/api_config")
def api_config_page(request: Request, s: Session = Depends(get_db)):
    configs = s.query(db.ApiConfig).all()
    presets = s.query(db.TaskPreset).all() # 新增：查询预设
    return templates.TemplateResponse("api_config.html", {
        "request": request, 
        "configs": configs, 
        "presets": presets
    })

@app.post("/api_config/add")
def add_api_config(name: str = Form(...), base_url: str = Form(...), api_key: str = Form(...), s: Session = Depends(get_db)):
    new_cfg = db.ApiConfig(name=name, base_url=base_url, api_key=api_key)
    s.add(new_cfg)
    s.commit()
    return RedirectResponse(url="/api_config", status_code=303)

@app.get("/api_config/get/{cfg_id}")
def get_api_config(cfg_id: int, s: Session = Depends(get_db)):
    cfg = s.query(db.ApiConfig).filter(db.ApiConfig.id == cfg_id).first()
    if not cfg: return JSONResponse(status_code=404, content={"message": "Not found"})
    return {"id": cfg.id, "name": cfg.name, "base_url": cfg.base_url, "api_key": cfg.api_key}

@app.post("/api_config/update")
def update_api_config(
    cfg_id: int = Form(...), 
    name: str = Form(...), 
    base_url: str = Form(...), 
    api_key: str = Form(...), 
    s: Session = Depends(get_db)
):
    cfg = s.query(db.ApiConfig).filter(db.ApiConfig.id == cfg_id).first()
    if cfg:
        cfg.name, cfg.base_url, cfg.api_key = name, base_url, api_key
        s.commit()
    return RedirectResponse(url="/api_config", status_code=303)

@app.post("/api_config/delete/{cfg_id}")
def delete_api_config(cfg_id: int, s: Session = Depends(get_db)):
    cfg = s.query(db.ApiConfig).filter(db.ApiConfig.id == cfg_id).first()
    if cfg:
        s.delete(cfg)
        s.commit()
    return RedirectResponse(url="/api_config", status_code=303)

# 添加预设
# 修改 presets/add 路由
@app.post("/presets/add")
def add_preset(name: str = Form(...), content: str = Form(...), s: Session = Depends(get_db)):
    new_pre = db.TaskPreset(name=name, content=content)
    s.add(new_pre)
    s.commit()
    # 关键修改：添加 #preset-pane 锚点
    return RedirectResponse(url="/api_config#preset-pane", status_code=303)

# 路由 1: 获取单条数据 (供 JS 调用填充弹窗)
@app.get("/presets/get/{pre_id}")
def get_preset(pre_id: int, s: Session = Depends(get_db)):
    print(f"正在后端获取预设数据, ID: {pre_id}") # 调试日志
    pre = s.query(db.TaskPreset).filter(db.TaskPreset.id == pre_id).first()
    if not pre:
        return JSONResponse(status_code=404, content={"message": "预设不存在"})
    
    # 显式返回字典，FastAPI 会自动将其转为 JSON
    return {
        "id": pre.id,
        "name": pre.name,
        "content": pre.content
    }

# 路由 2: 处理更新请求 (由弹窗 Form 提交)
@app.post("/presets/update")
def update_preset(
    pre_id: int = Form(...),   # 这里的变量名要和 HTML input 的 name 一致
    name: str = Form(...), 
    content: str = Form(...), 
    s: Session = Depends(get_db)
):
    pre = s.query(db.TaskPreset).filter(db.TaskPreset.id == pre_id).first()
    if pre:
        pre.name = name
        pre.content = content
        s.commit()
    # 关键修改：添加 #preset-pane 锚点
    return RedirectResponse(url="/api_config#preset-pane", status_code=303)

@app.post("/presets/delete/{pre_id}")
def delete_preset(pre_id: int, s: Session = Depends(get_db)):
    pre = s.query(db.TaskPreset).filter(db.TaskPreset.id == pre_id).first()
    if pre:
        s.delete(pre)
        s.commit()
    return RedirectResponse(url="/api_config#preset-pane", status_code=303)

# --- 路由 3: 创建抓取任务 ---
# 修改后的创建任务路由
@app.post("/tasks/create")
async def create_scrape_task(
    background_tasks: BackgroundTasks,
    task_name: str = Form(...),
    api_id: int = Form(...),
    model: str = Form(...),
    thinking: str = Form(...),
    prompts_text: str = Form(...),
    preset_id: int = Form(...), # 新增：接收预设ID
    s: Session = Depends(get_db)
):
    prompt_list = [p.strip() for p in prompts_text.split('\n') if p.strip()]
    
    # 获取预设内容
    preset = s.query(db.TaskPreset).filter(db.TaskPreset.id == preset_id).first()
    system_instruction = preset.content if preset else ""

    new_task = db.ScrapeTask(
        name=task_name,
        model=model,
        thinking_level=thinking,
        status="pending"
    )
    s.add(new_task)
    s.commit()

    # 将系统指令传递给后台任务
    background_tasks.add_task(
        start_batch_task, 
        new_task.id, 
        api_id, 
        prompt_list, 
        system_instruction # 传递指令
    )

    return RedirectResponse(url="/", status_code=303)

# --- 路由 4: 结果详情浏览 ---
@app.get("/results/{task_id}")
def view_results(task_id: int, request: Request, s: Session = Depends(get_db)):
    task = s.query(db.ScrapeTask).filter(db.ScrapeTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return templates.TemplateResponse("results.html", {"request": request, "task": task})

# 启动入口 (建议使用命令: uvicorn main:app --reload)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
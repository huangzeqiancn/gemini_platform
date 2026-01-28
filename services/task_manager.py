from database import SessionLocal, ScrapeTask, ApiConfig
from services.scraper import run_single_scrape

def start_batch_task(task_id, api_config_id, prompts, system_instruction):
    """
    批量处理任务
    """
    db = SessionLocal()
    task = db.query(ScrapeTask).filter_by(id=task_id).first()
    api_cfg = db.query(ApiConfig).filter_by(id=api_config_id).first()
    
    if not task or not api_cfg:
        return

    task.status = "running"
    db.commit()

    success_count = 0
    for p in prompts:
        # 调用上面 scraper.py 里的函数
        is_ok = run_single_scrape(
            api_cfg, 
            task.id, 
            p, 
            task.model, 
            task.thinking_level,
            system_template=system_instruction # 传入模板
        )
        if is_ok:
            success_count += 1
            
    # 更新任务状态
    task.status = "completed"
    db.commit()
    db.close()
    print(f"任务 {task_id} 执行完毕，成功: {success_count}/{len(prompts)}")
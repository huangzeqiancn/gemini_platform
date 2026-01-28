from database import init_db, SessionLocal, ApiConfig, ScrapeTask, TaskEntry, TaskPreset
import datetime

def test_database_flow():
    # 1. 初始化表 (关键：这会创建新增加的 task_presets 表)
    print("正在初始化数据库表结构...")
    init_db()
    db = SessionLocal()

    try:
        # 2. 模拟/初始化 API 配置
        print("检查 API 配置...")
        test_api = ApiConfig(
            name="GptsApi-Default",
            base_url="https://api.gptsapi.net/v1",
            api_key="sk-test-123456"
        )
        db.merge(test_api) # 存在则跳过，不存在则创建
        
        # 3. 新增：初始化“指令预设”模板
        # 这是解决“今天星期几”日期错误的核心地基
        print("检查指令预设模板...")
        web_preset = TaskPreset(
            name="Web模拟器 (时间注入)",
            content=(
                "You are Gemini 3, operating in a high-fidelity web-browser context.\n"
                "[Metadata]\n"
                "- Current Time: {{current_time}}\n"
                "- Day of Week: {{day_of_week}}\n"
                "- Location: Washington, DC\n\n"
                "[Instruction]\n"
                "Always use the provided Current Time as your reference date. "
                "If asked about 'today' or 'now', use this metadata to answer accurately."
            )
        )
        # 简单的查重检查，避免重复插入
        existing_preset = db.query(TaskPreset).filter_by(name=web_preset.name).first()
        if not existing_preset:
            db.add(web_preset)
            print(f"✅ 成功注入预设模板: {web_preset.name}")

        # 4. 创建一个测试抓取任务
        new_task = ScrapeTask(
            name="日期准确性测试任务",
            model="gemini-3-flash",
            thinking_level="medium",
            status="completed" # 模拟已完成
        )
        db.add(new_task)
        db.commit() # 获取 task.id
        print(f"创建测试任务成功: ID={new_task.id}")

        # 5. 存入模拟结果
        entry = TaskEntry(
            task_id=new_task.id,
            prompt="今天星期几？",
            answer="根据注入的上下文，今天是 2026年1月27日，星期二。",
            status="success",
            tokens_used=500
        )
        db.add(entry)
        db.commit()

        # 验证关系映射
        task = db.query(ScrapeTask).filter_by(id=new_task.id).first()
        print(f"\n--- 数据库验证完毕 ---")
        print(f"任务名称: {task.name}")
        print(f"关联结果数: {len(task.entries)}")
        print(f"可用预设模板: {[p.name for p in db.query(TaskPreset).all()]}")

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    test_database_flow()
    print("\n🚀 数据库环境已就绪，请启动 main.py 并使用『Web模拟器』模板进行测试！")
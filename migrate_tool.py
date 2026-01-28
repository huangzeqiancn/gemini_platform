# migrate_tool.py
import json
import os
from datetime import datetime
from sqlalchemy.orm import Session
from database import SessionLocal, engine, Base
import database as db  # 导入你的模型定义

def export_data():
    """全自动备份：导出所有已定义的表数据"""
    s = SessionLocal()
    backup = {}
    # 获取 Base 中注册的所有表名
    tables = Base.metadata.tables.keys()
    
    try:
        print("🔍 开始扫描数据库表...")
        for table_name in tables:
            # 动态获取模型类
            model = next((cls for cls in Base.__subclasses__() if cls.__tablename__ == table_name), None)
            if model:
                rows = s.query(model).all()
                backup[table_name] = [
                    {c.name: getattr(row, c.name) for c in row.__table__.columns} 
                    for row in rows
                ]
                print(f" - [备份] 表 {table_name}: {len(rows)} 条记录")
        
        with open("./data/full_system_backup.json", "w", encoding="utf-8") as f:
            json.dump(backup, f, ensure_ascii=False, indent=4, default=str)
        print(f"\n✅ 导出成功！备份文件位于: ./data/full_system_backup.json")
    except Exception as e:
        print(f"❌ 导出失败: {e}")
    finally:
        s.close()

def import_data():
    """全自动恢复：增加日期字段的解析逻辑"""
    backup_path = "./data/full_system_backup.json"
    if not os.path.exists(backup_path):
        print(f"❌ 找不到备份文件: {backup_path}")
        return

    s = SessionLocal()
    try:
        with open(backup_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        print("🚀 开始恢复数据并转换日期格式...")
        
        table_order = ["api_configs", "task_presets", "scrape_tasks", "task_entries"]
        
        for table_name in table_order:
            if table_name not in data:
                continue
            
            model = next((cls for cls in Base.__subclasses__() if cls.__tablename__ == table_name), None)
            if not model:
                continue
            
            inserted_count = 0
            for item in data[table_name]:
                valid_fields = {k: v for k, v in item.items() if k in model.__table__.columns}
                
                # --- 关键修复代码：处理日期字符串 ---
                for key, value in valid_fields.items():
                    # 如果字段名包含 'created_at' 或 'at'，且值是字符串，尝试转回 datetime
                    if 'created_at' in key and isinstance(value, str) and value != "None":
                        try:
                            # 适配 JSON 导出的 '2026-01-27 20:41:24.752971' 格式
                            valid_fields[key] = datetime.strptime(value.split('.')[0], '%Y-%m-%d %H:%M:%S')
                        except:
                            valid_fields[key] = datetime.now() # 如果解析失败，赋当前时间
                # ----------------------------------

                exists = s.query(model).filter(model.id == valid_fields['id']).first()
                if not exists:
                    s.add(model(**valid_fields))
                    inserted_count += 1
            
            s.flush() 
            print(f" - [恢复] 表 {table_name}: 已还原 {inserted_count} 条记录")
            
        s.commit()
        print("\n✅ 数据恢复成功！日期格式已校正。")
    except Exception as e:
        s.rollback()
        print(f"❌ 导入失败: {e}")
    finally:
        s.close()

if __name__ == "__main__":
    print("--- 数据库维护工具 (2026版) ---")
    print("1. 导出备份 (保命第一步)")
    print("2. 导入恢复 (重构后回灌)")
    choice = input("请选择操作: ")
    if choice == "1":
        export_data()
    elif choice == "2":
        import_data()
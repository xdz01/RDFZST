import sqlite3
from datetime import datetime, timedelta

def adjust_time_forward_8_hours():
    conn = sqlite3.connect('instance/rdfz.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # 开始事务
        cursor.execute("BEGIN TRANSACTION")
        
        # 1. 调整用户表的创建时间
        print("开始调整用户表的创建时间...")
        cursor.execute("SELECT id, created_at FROM users")
        users = cursor.fetchall()
        
        for user in users:
            old_time = datetime.strptime(user['created_at'], '%Y-%m-%d %H:%M:%S')
            new_time = old_time + timedelta(hours=8)
            cursor.execute(
                "UPDATE users SET created_at = ? WHERE id = ?",
                (new_time.strftime('%Y-%m-%d %H:%M:%S'), user['id'])
            )
        print(f"已更新 {len(users)} 条用户记录")
        
        # 2. 调整评论表的创建时间
        print("开始调整评论表的创建时间...")
        cursor.execute("SELECT id, created_at FROM reviews")
        reviews = cursor.fetchall()
        
        for review in reviews:
            old_time = datetime.strptime(review['created_at'], '%Y-%m-%d %H:%M:%S')
            new_time = old_time + timedelta(hours=8)
            cursor.execute(
                "UPDATE reviews SET created_at = ? WHERE id = ?",
                (new_time.strftime('%Y-%m-%d %H:%M:%S'), review['id'])
            )
        print(f"已更新 {len(reviews)} 条评论记录")
        
        # 提交事务
        conn.commit()
        print("所有时间调整完成并已提交")
        
    except Exception as e:
        conn.rollback()
        print(f"发生错误，已回滚: {str(e)}")
    finally:
        conn.close()

if __name__ == '__main__':
    print("警告：此操作将修改数据库中的所有用户和评论的创建时间，向后调整8小时")
    confirm = input("确定要执行此操作吗？(y/n): ").strip().lower()
    
    if confirm == 'y':
        print("开始执行时间调整...")
        adjust_time_forward_8_hours()
    else:
        print("操作已取消")
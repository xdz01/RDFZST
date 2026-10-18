import sqlite3
import os
import time
from werkzeug.security import generate_password_hash, check_password_hash

# 使用应用根目录（本文件所在目录）定位数据库，避免在服务器上因工作目录不同而找不到数据库
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, 'instance')
DB_PATH = os.path.join(INSTANCE_DIR, 'rdfz.db')

# Create database folder if it doesn't exist
if not os.path.exists(INSTANCE_DIR):
    os.makedirs(INSTANCE_DIR)

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    
    # 创建楼层表
    conn.execute('''
    CREATE TABLE IF NOT EXISTS floors (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT
    )
    ''')
    
    # 创建食物表
    conn.execute('''
    CREATE TABLE IF NOT EXISTS foods (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        floor_id INTEGER NOT NULL,
        meal_time TEXT,
        price REAL DEFAULT 0.0,
        description TEXT,
        cover_image TEXT,
        category TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (floor_id) REFERENCES floors (id)
    )
    ''')
    
    # 创建category字段（如果不存在）
    try:
        conn.execute('ALTER TABLE foods ADD COLUMN category TEXT')
        print("已添加foods表的category字段")
    except sqlite3.OperationalError:
        # 字段已存在，跳过
        pass
    
    # 创建图片表
    conn.execute('''
    CREATE TABLE IF NOT EXISTS images (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        food_id INTEGER NOT NULL,
        user_id INTEGER,
        filename TEXT NOT NULL,
        is_cover INTEGER DEFAULT 0,
        review_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (food_id) REFERENCES foods (id),
        FOREIGN KEY (user_id) REFERENCES users (id),
        FOREIGN KEY (review_id) REFERENCES reviews (id)
    )
    ''')
    
    # 检查images表是否有review_id列
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(images)")
        columns = cursor.fetchall()
        has_review_id = any(col['name'] == 'review_id' for col in columns)
        
        if not has_review_id:
            print("向images表添加review_id列...")
            conn.execute("ALTER TABLE images ADD COLUMN review_id INTEGER REFERENCES reviews(id)")
            conn.commit()
    except Exception as e:
        print(f"检查/修改表结构时出错: {e}")
    
    # 创建评论表
    conn.execute('''
    CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        food_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        rating INTEGER NOT NULL,
        comment TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (food_id) REFERENCES foods (id),
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')
    
    # 创建用户表
    conn.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        phone TEXT,
        role TEXT DEFAULT 'user',
        created_at TIMESTAMP DEFAULT (datetime('now', '+8 hours'))
    )
    ''')

    try:
        conn.execute('ALTER TABLE users ADD COLUMN avatar TEXT')
    except sqlite3.OperationalError:
        pass
    
    # 创建反馈表
    conn.execute('''
    CREATE TABLE IF NOT EXISTS feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT,
        email TEXT,
        subject TEXT NOT NULL,
        message TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')
    
    # 创建流量监测相关表
    # 访问日志表
    conn.execute('''
    CREATE TABLE IF NOT EXISTS access_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ip_address TEXT NOT NULL,
        user_agent TEXT,
        user_id INTEGER,
        username TEXT,
        endpoint TEXT NOT NULL,
        method TEXT NOT NULL,
        response_time REAL,
        bytes_sent INTEGER DEFAULT 0,
        status_code INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')
    
    # IP封锁记录表
    conn.execute('''
    CREATE TABLE IF NOT EXISTS ip_blocks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ip_address TEXT NOT NULL,
        reason TEXT NOT NULL,
        block_type TEXT NOT NULL,
        duration_hours INTEGER DEFAULT 24,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        expires_at TIMESTAMP,
        created_by TEXT DEFAULT 'system'
    )
    ''')
    
    # 流量统计表
    conn.execute('''
    CREATE TABLE IF NOT EXISTS traffic_stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ip_address TEXT NOT NULL,
        total_requests INTEGER DEFAULT 0,
        total_bytes INTEGER DEFAULT 0,
        avg_response_time REAL DEFAULT 0,
        last_access TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_blocked INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # 创建索引以提高查询性能
    conn.execute('CREATE INDEX IF NOT EXISTS idx_access_logs_ip ON access_logs(ip_address)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_access_logs_created_at ON access_logs(created_at)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_ip_blocks_ip ON ip_blocks(ip_address)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_traffic_stats_ip ON traffic_stats(ip_address)')

    conn.execute('''
    CREATE TABLE IF NOT EXISTS team_years (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        year INTEGER NOT NULL UNIQUE,
        title TEXT DEFAULT '',
        theme TEXT NOT NULL DEFAULT 'ink',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    conn.execute('''
    CREATE TABLE IF NOT EXISTS team_members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        year_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        role TEXT NOT NULL,
        department TEXT DEFAULT '',
        bio TEXT DEFAULT '',
        avatar TEXT,
        sort_order INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (year_id) REFERENCES team_years (id)
    )
    ''')
    _seed_team_if_empty(conn)
    
    conn.commit()
    conn.close()

def _seed_team_if_empty(conn):
    existing = conn.execute('SELECT COUNT(*) AS count FROM team_years').fetchone()
    if existing and existing['count']:
        return
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO team_years (year, title, theme) VALUES (?, ?, ?)',
        (2026, 'Aether', 'ink')
    )
    year_id = cursor.lastrowid
    members = [
        ('fyfy001', '设计开发', '人大附中编程社', ''),
        ('Jhua老师', '指导老师', '人大附中编程社', ''),
        ('段宗延', '开发', '人大附中人工智能社', ''),
        ('陈逸戈', '程序员', '编程社 / 人工智能社', ''),
        ('雷璐西', '管理运营', '饭否社', ''),
        ('王佳源', '管理运营', '饭否社', ''),
        ('顾雪隽', '管理运营', '饭否社', ''),
        ('倪若木', '管理运营', '饭否社', ''),
        ('蔡明翰', '管理运营', '饭否社', ''),
        ('李焓', '管理运营', '饭否社', ''),
    ]
    for index, member in enumerate(members):
        cursor.execute(
            '''INSERT INTO team_members (year_id, name, role, department, bio, sort_order)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (year_id, member[0], member[1], member[2], member[3], index)
        )

# User management functions
def register_user(username, password, phone):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        hashed_password = generate_password_hash(password)
        cursor.execute(
            '''INSERT INTO users (username, password, phone, created_at)
               VALUES (?, ?, ?, datetime('now', '+8 hours'))''',
            (username, hashed_password, phone)
        )
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()
        return user_id
    except sqlite3.IntegrityError:
        conn.close()
        return None

def authenticate_user(username, password):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
    user = cursor.fetchone()
    conn.close()
    
    if user and check_password_hash(user['password'], password):
        return dict(user)
    return None

def get_user_by_id(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    
    if user:
        return dict(user)
    return None

def set_user_avatar(user_id, filename):
    conn = get_db_connection()
    conn.execute('UPDATE users SET avatar = ? WHERE id = ?', (filename, user_id))
    conn.commit()
    conn.close()

def update_user_password(user_id, new_password):
    conn = get_db_connection()
    hashed_password = generate_password_hash(new_password)
    conn.execute('UPDATE users SET password = ? WHERE id = ?', (hashed_password, user_id))
    conn.commit()
    conn.close()

# Floor and food management functions
def get_all_floors():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM floors ORDER BY id')
    floors = cursor.fetchall()
    conn.close()
    
    return [dict(floor) for floor in floors]

def get_food_by_floor(floor_id, meal_time=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        query = '''
            SELECT f.*, fl.name as floor_name, 
                   (SELECT AVG(rating) FROM reviews WHERE food_id = f.id) as avg_rating,
                   f.cover_image
            FROM foods f
            JOIN floors fl ON f.floor_id = fl.id
            WHERE f.floor_id = ?
        '''
        params = [floor_id]
        
        if meal_time:
            query += ' AND (f.meal_time = ? OR f.meal_time IS NULL)'
            params.append(meal_time)
        
        cursor.execute(query, tuple(params))
        foods = [dict(food) for food in cursor.fetchall()]
        
        # 处理avg_rating为None的情况
        for food in foods:
            if food['avg_rating'] is None:
                food['avg_rating'] = 5.0  # 无评论时默认为5星
            
            # 如果cover_image是None但foods表中没有记录，尝试从images表获取
            if food['cover_image'] is None:
                cursor.execute('''
                    SELECT filename FROM images 
                    WHERE food_id = ? AND is_cover = 1 
                    LIMIT 1
                ''', (food['id'],))
                cover = cursor.fetchone()
                if cover:
                    food['cover_image'] = cover['filename']
            
            # 获取评论列表
            cursor.execute('''
                SELECT r.*, u.username, u.role
                FROM reviews r
                JOIN users u ON r.user_id = u.id
                WHERE r.food_id = ?
                ORDER BY r.created_at DESC
            ''', (food['id'],))
            food['reviews'] = [dict(review) for review in cursor.fetchall()]
        
        return foods
    except sqlite3.Error as e:
        print(f"Database error in get_food_by_floor: {e}")
        return []
    finally:
        conn.close()

def get_food_by_id(food_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT f.*, fl.name as floor_name
            FROM foods f
            JOIN floors fl ON f.floor_id = fl.id
            WHERE f.id = ?
        ''', (food_id,))
        
        food = cursor.fetchone()
        
        if food:
            # 获取食物评论
            cursor.execute('''
                SELECT r.*, u.username, u.role, u.avatar
                FROM reviews r
                JOIN users u ON r.user_id = u.id
                WHERE r.food_id = ?
                ORDER BY r.created_at DESC
            ''', (food_id,))
            
            reviews = cursor.fetchall()
            
            # 获取食物图片
            cursor.execute('SELECT * FROM images WHERE food_id = ?', (food_id,))
            images = cursor.fetchall()
            
            # 构建完整的食物对象
            food_dict = dict(food)
            food_dict['reviews'] = [dict(review) for review in reviews]
            food_dict['images'] = [dict(image) for image in images]
            
            # 确保cover_image是字符串类型
            if food_dict.get('cover_image') is not None:
                if isinstance(food_dict['cover_image'], dict):
                    food_dict['cover_image'] = food_dict['cover_image'].get('filename', '')
            else:
                # 如果没有封面图片，寻找一个可用的图片作为封面
                for image in images:
                    if image['is_cover'] == 1:
                        food_dict['cover_image'] = image['filename']
                        break
                else:
                    # 如果没有指定封面，使用第一张图片
                    if images:
                        food_dict['cover_image'] = images[0]['filename']
                    else:
                        food_dict['cover_image'] = ''
            
            return food_dict
        
        return None
    except sqlite3.Error as e:
        print(f"Database error in get_food_by_id: {e}")
        return None
    finally:
        conn.close()

def add_food_item(name, description, floor_id, meal_time, user_id, price=0.0, category=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO foods (name, description, floor_id, meal_time, price, category)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (name, description, floor_id, meal_time, price, category))
        
        food_id = cursor.lastrowid
        conn.commit()
        return food_id
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Database error in add_food_item: {e}")
        return None
    finally:
        conn.close()

def update_food_item(food_id, name, description=None, floor_id=None, meal_time=None, price=None, category=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # 构建更新语句和参数
        update_fields = ['name = ?']
        params = [name]
        
        if description is not None:
            update_fields.append('description = ?')
            params.append(description)
        
        if floor_id is not None:
            update_fields.append('floor_id = ?')
            params.append(floor_id)
        
        if meal_time is not None:
            update_fields.append('meal_time = ?')
            params.append(meal_time)
        
        if price is not None:
            update_fields.append('price = ?')
            params.append(price)
            
        if category is not None:
            update_fields.append('category = ?')
            params.append(category)
        
        # 添加food_id作为WHERE条件的参数
        params.append(food_id)
        
        # 执行更新
        query = f'''
            UPDATE foods
            SET {', '.join(update_fields)}
            WHERE id = ?
        '''
        
        cursor.execute(query, params)
        conn.commit()
        return True
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Database error in update_food_item: {e}")
        return False
    finally:
        conn.close()

def delete_food_item(food_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Delete associated reviews
        cursor.execute('DELETE FROM reviews WHERE food_id = ?', (food_id,))
        
        # Delete associated images
        cursor.execute('DELETE FROM images WHERE food_id = ?', (food_id,))
        
        # Delete the food item
        cursor.execute('DELETE FROM foods WHERE id = ?', (food_id,))
        
        conn.commit()
        return True
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Database error in delete_food_item: {e}")
        return False
    finally:
        conn.close()

# Review functions
def add_review(food_id, user_id, rating, comment):
    print(f"add_review调用: food_id={food_id}, user_id={user_id}, rating={rating}, comment={comment[:20] if comment else None}...")
    
    # 输入验证
    if not food_id or not user_id:
        print("错误: food_id或user_id为空")
        return False
    
    if not rating or not isinstance(rating, int) or not 1 <= rating <= 5:
        print(f"无效的评分值: {rating}，类型={type(rating)}")
        return False
    
    if not comment or not isinstance(comment, str):
        print(f"无效的评论: {comment}，类型={type(comment)}")
        return False
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # 检查food_id是否有效
        cursor.execute('SELECT id FROM foods WHERE id = ?', (food_id,))
        if not cursor.fetchone():
            print(f"错误: 无效的food_id {food_id}")
            return False
        
        # 检查user_id是否有效
        cursor.execute('SELECT id FROM users WHERE id = ?', (user_id,))
        if not cursor.fetchone():
            print(f"错误: 无效的user_id {user_id}")
            return False
        
        # 检查是否已经存在此用户对此食品的评论
        cursor.execute('''
            SELECT id FROM reviews 
            WHERE food_id = ? AND user_id = ?
        ''', (food_id, user_id))
        
        existing_review = cursor.fetchone()
        
        if existing_review:
            # 更新已有评论 - 使用datetime('now', 'localtime')获取北京时间
            try:
                cursor.execute('''
                    UPDATE reviews 
                    SET rating = ?, comment = ?, created_at = datetime('now', 'localtime')
                    WHERE id = ?
                ''', (rating, comment, existing_review['id']))
                
                review_id = existing_review['id']
                print(f"成功更新现有评论 id={review_id}")
            except sqlite3.Error as e:
                print(f"更新评论时出错: {e}")
                return False
        else:
            # 添加新评论 - 明确指定created_at为北京时间
            try:
                cursor.execute('''
                    INSERT INTO reviews (food_id, user_id, rating, comment, created_at)
                    VALUES (?, ?, ?, ?, datetime('now', 'localtime'))
                ''', (food_id, user_id, rating, comment))
                
                review_id = cursor.lastrowid
                print(f"成功添加新评论 id={review_id}")
            except sqlite3.Error as e:
                print(f"插入评论时出错: {e}")
                return False
        
        # 更新食品的平均评分
        try:
            cursor.execute('''
                UPDATE foods
                SET avg_rating = (
                    SELECT AVG(rating) 
                    FROM reviews 
                    WHERE food_id = ?
                )
                WHERE id = ?
            ''', (food_id, food_id))
            
            print(f"已更新food_id={food_id}的平均评分")
        except sqlite3.Error as e:
            print(f"更新平均评分时出错: {e}")
            # 不中断操作，即使平均评分更新失败
        
        conn.commit()
        print("评论操作成功提交到数据库")
        return True
    except sqlite3.Error as e:
        conn.rollback()
        print(f"数据库错误 in add_review: {e}")
        return False
    except Exception as e:
        conn.rollback()
        print(f"未预期的错误 in add_review: {e}")
        return False
    finally:
        conn.close()
def get_user_reviews(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT r.*, f.name as food_name, f.floor_id
        FROM reviews r
        JOIN foods f ON r.food_id = f.id
        WHERE r.user_id = ?
        ORDER BY r.created_at DESC
    ''', (user_id,))
    
    reviews = cursor.fetchall()
    conn.close()
    
    return [dict(review) for review in reviews]

def delete_review(review_id, user_id=None, is_admin=False):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # 检查评论是否存在
        cursor.execute('SELECT * FROM reviews WHERE id = ?', (review_id,))
        review = cursor.fetchone()
        
        if not review:
            print(f"Error: Review ID {review_id} not found")
            return False
        
        # 如果非管理员，检查是否是评论所有者
        if not is_admin and review['user_id'] != user_id:
            print(f"Permission denied: User ID {user_id} cannot delete review ID {review_id}")
            return False
        
        # 执行删除
        cursor.execute('DELETE FROM reviews WHERE id = ?', (review_id,))
        
        # 尝试删除与该评论关联的图片
        cursor.execute('SELECT id FROM images WHERE review_id = ?', (review_id,))
        associated_images = cursor.fetchall()
        
        for image in associated_images:
            delete_image(image['id'], is_admin=True)
            print(f"Deleted image {image['id']} associated with review {review_id}")
        
        conn.commit()
        print(f"成功删除评论 ID: {review_id}")
        return True
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Database error in delete_review: {e}")
        return False
    finally:
        conn.close()

# Image management functions
def add_image(food_id, user_id, filename, is_cover=False, review_id=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        if is_cover:
            # If this is a cover image, reset any existing cover image
            cursor.execute('''
                UPDATE images
                SET is_cover = 0
                WHERE food_id = ?
            ''', (food_id,))
        
        # 添加图片记录，如果有评论ID则与评论关联
        if review_id:
            cursor.execute('''
                INSERT INTO images (food_id, user_id, filename, is_cover, review_id)
                VALUES (?, ?, ?, ?, ?)
            ''', (food_id, user_id, filename, is_cover, review_id))
        else:
            cursor.execute('''
                INSERT INTO images (food_id, user_id, filename, is_cover)
                VALUES (?, ?, ?, ?)
            ''', (food_id, user_id, filename, is_cover))
        
        # If this is a cover image, update the food item
        if is_cover:
            cursor.execute('''
                UPDATE foods
                SET cover_image = ?
                WHERE id = ?
            ''', (filename, food_id))
        
        conn.commit()
        return True
    except sqlite3.Error as e:
        conn.rollback()
        print(f"数据库错误 in add_image: {e}")
        return False
    finally:
        conn.close()

def set_image_as_cover(image_id, food_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        print(f"\n==== 设置图片ID={image_id}为食品ID={food_id}的封面 ====")
        
        # 确认图片存在并获取文件名
        cursor.execute('SELECT * FROM images WHERE id = ?', (image_id,))
        image = cursor.fetchone()
        
        if not image:
            print(f"错误: 图片ID={image_id}不存在")
            return False
        
        filename = image['filename']
        print(f"找到图片: filename={filename}")
        
        # 确认该图片属于指定的食品
        if image['food_id'] != food_id:
            print(f"错误: 图片ID={image_id}不属于食品ID={food_id}")
            return False
            
        # 开始事务
        cursor.execute('BEGIN TRANSACTION')
        
        # 重置该食品的所有图片is_cover标志
        cursor.execute('''
            UPDATE images
            SET is_cover = 0
            WHERE food_id = ?
        ''', (food_id,))
        reset_count = cursor.rowcount
        print(f"重置了{reset_count}张图片的is_cover标志")
        
        # 设置新的封面图片
        cursor.execute('''
            UPDATE images
            SET is_cover = 1
            WHERE id = ?
        ''', (image_id,))
        updated_count = cursor.rowcount
        print(f"设置图片is_cover=1: 更新了{updated_count}行")
        
        # 更新食品表中的cover_image字段
        cursor.execute('''
            UPDATE foods
            SET cover_image = ?
            WHERE id = ?
        ''', (filename, food_id))
        food_updated = cursor.rowcount
        print(f"更新food表的cover_image字段: 更新了{food_updated}行")
        
        # 提交事务
        conn.commit()
        print(f"事务已提交，成功将图片ID={image_id}设为食品ID={food_id}的封面")
        print(f"==== 设置封面完成 ====\n")
        return True
    except sqlite3.Error as e:
        conn.rollback()
        print(f"数据库错误 in set_image_as_cover: {e}")
        return False
    finally:
        conn.close()

def delete_image(image_id, user_id=None, is_admin=False):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # 检查图片是否存在
        cursor.execute('SELECT * FROM images WHERE id = ?', (image_id,))
        image = cursor.fetchone()
        
        if not image:
            print(f"错误: 图片ID {image_id} 不存在")
            return False
        
        # 检查权限
        if not is_admin and image['user_id'] != user_id:
            print(f"权限错误: 用户ID {user_id} 无权删除图片ID {image_id}")
            return False
        
        food_id = image['food_id']
        filename = image['filename']
        is_cover = image['is_cover']
        
        # 检查这张图片是否是cover_image
        cursor.execute('SELECT cover_image FROM foods WHERE id = ?', (food_id,))
        food = cursor.fetchone()
        if food and food['cover_image'] == filename:
            is_food_cover = True
            print(f"要删除的图片是food表中的cover_image: {filename}")
        else:
            is_food_cover = False
        
        # 先查询剩余图片数量(除了要删除的这张)
        cursor.execute('SELECT COUNT(*) as count FROM images WHERE food_id = ? AND id != ?', (food_id, image_id))
        remaining_count = cursor.fetchone()['count']
        print(f"删除前，食品ID={food_id}剩余图片数量(不包括当前): {remaining_count}")
        
        # 再删除图片记录
        cursor.execute('DELETE FROM images WHERE id = ?', (image_id,))
        
        # 如果这是封面图片或者是food表中的cover_image，或者删除后没有图片了，则处理cover_image
        if is_cover == 1 or is_food_cover or remaining_count == 0:
            if remaining_count > 0:
                # 仍有其他图片，找一张作为新封面
                cursor.execute('''
                    SELECT id, filename 
                    FROM images 
                    WHERE food_id = ? 
                    ORDER BY created_at DESC 
                    LIMIT 1
                ''', (food_id,))
                
                next_image = cursor.fetchone()
                if next_image:
                    # 设置新的封面图片
                    cursor.execute('''
                        UPDATE images
                        SET is_cover = 1
                        WHERE id = ?
                    ''', (next_image['id'],))
                    
                    cursor.execute('''
                        UPDATE foods
                        SET cover_image = ?
                        WHERE id = ?
                    ''', (next_image['filename'], food_id))
                    print(f"已将图片ID={next_image['id']}设为新的封面图片")
            else:
                # 没有图片了，清除封面
                cursor.execute('''
                    UPDATE foods
                    SET cover_image = NULL
                    WHERE id = ?
                ''', (food_id,))
                print(f"已清除food_id={food_id}的封面图片，因为没有剩余图片")
        
        conn.commit()
        
        # 尝试从磁盘删除文件
        try:
            file_path = os.path.join('static/uploads', filename)
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"已从磁盘删除图片文件: {file_path}")
        except Exception as e:
            print(f"删除图片文件时出错: {e}")
        
        return True
    except sqlite3.Error as e:
        conn.rollback()
        print(f"数据库错误 in delete_image: {e}")
        return False
    finally:
        conn.close()

# Feedback functions
def add_feedback(name, email, message, user_id=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO feedback (user_id, name, email, message)
        VALUES (?, ?, ?, ?)
    ''', (user_id, name, email, message))
    
    conn.commit()
    conn.close()
    
    return True

def get_all_feedback(include_read=False):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if include_read:
        cursor.execute('''
            SELECT f.*, u.username
            FROM feedback f
            LEFT JOIN users u ON f.user_id = u.id
            ORDER BY f.is_read, f.created_at DESC
        ''')
    else:
        cursor.execute('''
            SELECT f.*, u.username
            FROM feedback f
            LEFT JOIN users u ON f.user_id = u.id
            WHERE f.is_read = 0
            ORDER BY f.created_at DESC
        ''')
    
    feedback = cursor.fetchall()
    conn.close()
    
    return [dict(item) for item in feedback]

def respond_to_feedback(feedback_id, response):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE feedback
        SET response = ?, is_read = 1
        WHERE id = ?
    ''', (response, feedback_id))
    
    conn.commit()
    conn.close()
    
    return True

# User management for admin functions
def get_all_users(sort_by='username', order='asc'):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 验证排序字段
    valid_sort_fields = ['username', 'phone', 'role', 'created_at']
    if sort_by not in valid_sort_fields:
        sort_by = 'username'
    
    # 验证排序方向
    if order.lower() not in ['asc', 'desc']:
        order = 'asc'
    
    # 构建SQL查询
    query = f'SELECT id, username, phone, role, created_at FROM users ORDER BY {sort_by} {order.upper()}'
    cursor.execute(query)
    users = cursor.fetchall()
    conn.close()
    
    return [dict(user) for user in users]

def update_user_role(user_id, role):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('UPDATE users SET role = ? WHERE id = ?', (role, user_id))
    conn.commit()
    conn.close()
    
    return True

def delete_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if the user exists and is not a superadmin
    cursor.execute('SELECT role FROM users WHERE id = ?', (user_id,))
    user = cursor.fetchone()
    
    if not user or user['role'] == 'superadmin':
        conn.close()
        return False
    
    # Delete the user's reviews
    cursor.execute('DELETE FROM reviews WHERE user_id = ?', (user_id,))
    
    # Get the user's images
    cursor.execute('SELECT id FROM images WHERE user_id = ?', (user_id,))
    images = cursor.fetchall()
    
    # Delete each image properly
    for image in images:
        delete_image(image['id'], is_admin=True)
    
    # Delete the user's feedback
    cursor.execute('DELETE FROM feedback WHERE user_id = ?', (user_id,))
    
    # Finally, delete the user
    cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
    
    conn.commit()
    conn.close()
    
    return True

# 获取楼层信息
def get_floor_by_id(floor_id):
    conn = get_db_connection()
    floor = conn.execute('SELECT * FROM floors WHERE id = ?', (floor_id,)).fetchone()
    conn.close()
    return floor

# Initialize the database
init_db() 

# 流量监测相关函数
def log_access(ip_address, user_agent, user_id, username, endpoint, method, response_time, bytes_sent, status_code):
    """记录访问日志"""
    conn = get_db_connection()
    try:
        conn.execute('''
            INSERT INTO access_logs (ip_address, user_agent, user_id, username, endpoint, method, response_time, bytes_sent, status_code)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (ip_address, user_agent, user_id, username, endpoint, method, response_time, bytes_sent, status_code))
        
        # 更新流量统计
        update_traffic_stats(conn, ip_address, response_time, bytes_sent)
        
        conn.commit()
    except Exception as e:
        print(f"记录访问日志时出错: {e}")
    finally:
        conn.close()

def update_traffic_stats(conn, ip_address, response_time, bytes_sent):
    """更新流量统计"""
    try:
        # 检查是否已有该IP的统计记录
        existing = conn.execute('SELECT * FROM traffic_stats WHERE ip_address = ?', (ip_address,)).fetchone()
        
        if existing:
            # 更新现有记录
            total_requests = existing['total_requests'] + 1
            total_bytes = existing['total_bytes'] + bytes_sent
            avg_response_time = ((existing['avg_response_time'] * existing['total_requests']) + response_time) / total_requests
            
            conn.execute('''
                UPDATE traffic_stats 
                SET total_requests = ?, total_bytes = ?, avg_response_time = ?, last_access = CURRENT_TIMESTAMP
                WHERE ip_address = ?
            ''', (total_requests, total_bytes, avg_response_time, ip_address))
        else:
            # 创建新记录
            conn.execute('''
                INSERT INTO traffic_stats (ip_address, total_requests, total_bytes, avg_response_time)
                VALUES (?, 1, ?, ?)
            ''', (ip_address, bytes_sent, response_time))
    except Exception as e:
        print(f"更新流量统计时出错: {e}")

def get_traffic_stats(limit=100):
    """获取流量统计"""
    conn = get_db_connection()
    try:
        # 获取实时流量统计，直接从access_logs表计算
        stats = conn.execute('''
            SELECT 
                ip_address,
                COUNT(*) as total_requests,
                SUM(bytes_sent) as total_bytes,
                AVG(response_time) as avg_response_time,
                MAX(created_at) as last_access,
                MIN(created_at) as first_access,
                COUNT(CASE WHEN created_at >= datetime('now', '-1 hour') THEN 1 END) as hour_requests,
                SUM(CASE WHEN created_at >= datetime('now', '-1 hour') THEN bytes_sent ELSE 0 END) as hour_bytes,
                COUNT(CASE WHEN created_at >= datetime('now', '-24 hours') THEN 1 END) as day_requests,
                SUM(CASE WHEN created_at >= datetime('now', '-24 hours') THEN bytes_sent ELSE 0 END) as day_bytes,
                CASE WHEN EXISTS (
                    SELECT 1 FROM ip_blocks 
                    WHERE ip_blocks.ip_address = access_logs.ip_address 
                    AND ip_blocks.is_active = 1
                ) THEN 1 ELSE 0 END as is_blocked
            FROM access_logs 
            GROUP BY ip_address
            ORDER BY total_requests DESC, last_access DESC 
            LIMIT ?
        ''', (limit,)).fetchall()
        return stats
    except Exception as e:
        print(f"获取流量统计时出错: {e}")
        return []
    finally:
        conn.close()

def get_access_logs(limit=100, ip_address=None):
    """获取访问日志"""
    conn = get_db_connection()
    try:
        if ip_address:
            logs = conn.execute('''
                SELECT * FROM access_logs 
                WHERE ip_address = ?
                ORDER BY created_at DESC 
                LIMIT ?
            ''', (ip_address, limit)).fetchall()
        else:
            logs = conn.execute('''
                SELECT * FROM access_logs 
                ORDER BY created_at DESC 
                LIMIT ?
            ''', (limit,)).fetchall()
        return logs
    except Exception as e:
        print(f"获取访问日志时出错: {e}")
        return []
    finally:
        conn.close()

def get_ip_blocks():
    """获取IP封锁记录"""
    conn = get_db_connection()
    try:
        blocks = conn.execute('''
            SELECT * FROM ip_blocks 
            ORDER BY created_at DESC
        ''').fetchall()
        return blocks
    except Exception as e:
        print(f"获取IP封锁记录时出错: {e}")
        return []
    finally:
        conn.close()

def block_ip(ip_address, reason, block_type, duration_hours=24, created_by='system'):
    """封锁IP地址"""
    conn = get_db_connection()
    try:
        # 检查该IP是否已经被有效封锁
        existing_block = conn.execute('''
            SELECT * FROM ip_blocks 
            WHERE ip_address = ? AND is_active = 1 
            AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
        ''', (ip_address,)).fetchone()
        
        # 如果已经存在有效封锁记录，不重复添加
        if existing_block:
            print(f"IP {ip_address} 已经被封锁，跳过重复封锁")
            return True
        
        # 计算过期时间 - duration_hours=0表示永久封锁
        import datetime
        if duration_hours == 0:
            expires_at = None  # 永久封锁，不设置过期时间
        else:
            expires_at = datetime.datetime.now() + datetime.timedelta(hours=duration_hours)
        
        conn.execute('''
            INSERT INTO ip_blocks (ip_address, reason, block_type, duration_hours, expires_at, created_by)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (ip_address, reason, block_type, duration_hours, expires_at, created_by))
        
        # 更新流量统计中的封锁状态
        conn.execute('UPDATE traffic_stats SET is_blocked = 1 WHERE ip_address = ?', (ip_address,))
        
        conn.commit()
        return True
    except Exception as e:
        print(f"封锁IP时出错: {e}")
        return False
    finally:
        conn.close()

def unblock_ip(ip_address):
    """解除IP封锁"""
    conn = get_db_connection()
    try:
        conn.execute('UPDATE ip_blocks SET is_active = 0 WHERE ip_address = ?', (ip_address,))
        conn.execute('UPDATE traffic_stats SET is_blocked = 0 WHERE ip_address = ?', (ip_address,))
        conn.commit()
        return True
    except Exception as e:
        print(f"解除IP封锁时出错: {e}")
        return False
    finally:
        conn.close()

def is_ip_blocked(ip_address):
    """检查IP是否被封锁"""
    conn = get_db_connection()
    try:
        # 检查是否有有效的封锁记录 - 支持永久封锁
        block = conn.execute('''
            SELECT * FROM ip_blocks 
            WHERE ip_address = ? AND is_active = 1 
            AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
        ''', (ip_address,)).fetchone()
        return block is not None
    except Exception as e:
        print(f"检查IP封锁状态时出错: {e}")
        return False
    finally:
        conn.close()

def cleanup_duplicate_ip_blocks():
    """清理重复的IP封锁记录，只保留最新的有效记录"""
    conn = get_db_connection()
    try:
        # 查找重复的IP封锁记录
        duplicates = conn.execute('''
            SELECT ip_address, COUNT(*) as count
            FROM ip_blocks 
            WHERE is_active = 1 
            AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
            GROUP BY ip_address 
            HAVING COUNT(*) > 1
        ''').fetchall()
        
        cleaned_count = 0
        for duplicate in duplicates:
            ip_address = duplicate['ip_address']
            
            # 获取该IP的所有有效封锁记录，按创建时间降序排列
            records = conn.execute('''
                SELECT id, created_at
                FROM ip_blocks 
                WHERE ip_address = ? AND is_active = 1 
                AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
                ORDER BY created_at DESC
            ''', (ip_address,)).fetchall()
            
            # 保留最新的记录，将其他记录标记为无效
            if len(records) > 1:
                latest_id = records[0]['id']
                for record in records[1:]:
                    conn.execute('UPDATE ip_blocks SET is_active = 0 WHERE id = ?', (record['id'],))
                    cleaned_count += 1
                
                print(f"清理IP {ip_address} 的重复封锁记录，保留最新记录 ID: {latest_id}")
        
        conn.commit()
        print(f"总共清理了 {cleaned_count} 条重复的IP封锁记录")
        return cleaned_count
        
    except Exception as e:
        print(f"清理重复IP封锁记录时出错: {e}")
        return 0
    finally:
        conn.close()

def cleanup_expired_blocks():
    """清理过期的封锁记录"""
    conn = get_db_connection()
    try:
        # 只清理有过期时间的封锁记录，永久封锁不清理
        conn.execute('UPDATE ip_blocks SET is_active = 0 WHERE expires_at IS NOT NULL AND expires_at <= CURRENT_TIMESTAMP')
        conn.commit()
    except Exception as e:
        print(f"清理过期封锁记录时出错: {e}")
    finally:
        conn.close()

def get_traffic_summary():
    """获取流量总览"""
    conn = get_db_connection()
    try:
        # 总访问量
        total_requests = conn.execute('SELECT COUNT(*) as count FROM access_logs').fetchone()['count']
        
        # 总流量（字节）
        total_bytes = conn.execute('SELECT SUM(bytes_sent) as total FROM access_logs').fetchone()['total'] or 0
        
        # 今日访问量
        today_requests = conn.execute('SELECT COUNT(*) as count FROM access_logs WHERE DATE(created_at) = DATE("now")').fetchone()['count']
        
        # 今日流量
        today_bytes = conn.execute('SELECT SUM(bytes_sent) as total FROM access_logs WHERE DATE(created_at) = DATE("now")').fetchone()['total'] or 0
        
        # 最近一小时访问量
        hour_requests = conn.execute('SELECT COUNT(*) as count FROM access_logs WHERE created_at >= datetime("now", "-1 hour")').fetchone()['count']
        
        # 最近一小时流量
        hour_bytes = conn.execute('SELECT SUM(bytes_sent) as total FROM access_logs WHERE created_at >= datetime("now", "-1 hour")').fetchone()['total'] or 0
        
        # 活跃IP数（最近一小时）
        active_ips = conn.execute('SELECT COUNT(DISTINCT ip_address) as count FROM access_logs WHERE created_at >= datetime("now", "-1 hour")').fetchone()['count']
        
        # 被封锁的IP数（包括永久封锁）
        blocked_ips = conn.execute('SELECT COUNT(*) as count FROM ip_blocks WHERE is_active = 1').fetchone()['count']
        
        # 永久封锁的IP数
        permanent_blocks = conn.execute('SELECT COUNT(*) as count FROM ip_blocks WHERE is_active = 1 AND expires_at IS NULL').fetchone()['count']
        
        return {
            'total_requests': total_requests,
            'total_bytes': total_bytes,
            'today_requests': today_requests,
            'today_bytes': today_bytes,
            'hour_requests': hour_requests,
            'hour_bytes': hour_bytes,
            'active_ips': active_ips,
            'blocked_ips': blocked_ips,
            'permanent_blocks': permanent_blocks
        }
    except Exception as e:
        print(f"获取流量总览时出错: {e}")
        return {}
    finally:
        conn.close()

def get_team_years_with_members():
    conn = get_db_connection()
    years = [dict(row) for row in conn.execute('SELECT * FROM team_years ORDER BY year DESC')]
    members = [dict(row) for row in conn.execute(
        'SELECT * FROM team_members ORDER BY sort_order, id'
    )]
    conn.close()
    grouped = {year['id']: [] for year in years}
    for member in members:
        if member['year_id'] in grouped:
            grouped[member['year_id']].append(member)
    for year in years:
        year['members'] = grouped[year['id']]
    return years

def get_team_year(year_id):
    conn = get_db_connection()
    row = conn.execute('SELECT * FROM team_years WHERE id = ?', (year_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def create_team_year(year, title, theme):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO team_years (year, title, theme) VALUES (?, ?, ?)',
            (year, title, theme)
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()

def update_team_year(year_id, year, title, theme):
    conn = get_db_connection()
    try:
        conn.execute(
            'UPDATE team_years SET year = ?, title = ?, theme = ? WHERE id = ?',
            (year, title, theme, year_id)
        )
        conn.commit()
    finally:
        conn.close()

def delete_team_year(year_id):
    conn = get_db_connection()
    avatars = [
        row['avatar'] for row in conn.execute(
            'SELECT avatar FROM team_members WHERE year_id = ? AND avatar IS NOT NULL',
            (year_id,)
        )
    ]
    conn.execute('DELETE FROM team_members WHERE year_id = ?', (year_id,))
    conn.execute('DELETE FROM team_years WHERE id = ?', (year_id,))
    conn.commit()
    conn.close()
    return avatars

def get_team_member(member_id):
    conn = get_db_connection()
    row = conn.execute('SELECT * FROM team_members WHERE id = ?', (member_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def create_team_member(year_id, name, role, department, bio, avatar):
    conn = get_db_connection()
    cursor = conn.cursor()
    current = cursor.execute(
        'SELECT COALESCE(MAX(sort_order), -1) AS max_order FROM team_members WHERE year_id = ?',
        (year_id,)
    ).fetchone()
    sort_order = (current['max_order'] if current else -1) + 1
    cursor.execute(
        '''INSERT INTO team_members (year_id, name, role, department, bio, avatar, sort_order)
           VALUES (?, ?, ?, ?, ?, ?, ?)''',
        (year_id, name, role, department, bio, avatar, sort_order)
    )
    conn.commit()
    member_id = cursor.lastrowid
    conn.close()
    return member_id

def update_team_member(member_id, year_id, name, role, department, bio, avatar):
    conn = get_db_connection()
    conn.execute(
        '''UPDATE team_members
           SET year_id = ?, name = ?, role = ?, department = ?, bio = ?, avatar = ?
           WHERE id = ?''',
        (year_id, name, role, department, bio, avatar, member_id)
    )
    conn.commit()
    conn.close()

def delete_team_member(member_id):
    conn = get_db_connection()
    row = conn.execute('SELECT avatar FROM team_members WHERE id = ?', (member_id,)).fetchone()
    conn.execute('DELETE FROM team_members WHERE id = ?', (member_id,))
    conn.commit()
    conn.close()
    return row['avatar'] if row else None
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort, jsonify, make_response
import os
import secrets
from werkzeug.utils import secure_filename
from PIL import Image
import time
import database as db
import sqlite3
import uuid
import datetime
import random
import string
from io import BytesIO
import base64
import pytz

app = Flask(__name__)
app.secret_key = 'rdfzcafeteriareview'  # Secret key for session management
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max upload
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

# 流量监测配置 - 已禁用
app.config['TRAFFIC_MONITORING'] = False
app.config['MAX_BANDWIDTH_PER_MINUTE'] = 50 * 1024 * 1024  # 每分钟最大带宽 (50MB)
app.config['MAX_BANDWIDTH_PER_2_HOURS'] = 150 * 1024 * 1024  # 120分钟内最大带宽 (150MB)
app.config['MAX_BANDWIDTH_PER_DAY'] = 300 * 1024 * 1024  # 一天内最大带宽 (300MB)
app.config['AUTO_BLOCK_ENABLED'] = False

# 时区配置
app.config['TIMEZONE'] = 'Asia/Shanghai'  # 北京时间

# 初始化数据库
db.init_db()

# 时区工具函数
def get_beijing_time():
    """获取北京时间"""
    beijing_tz = pytz.timezone(app.config['TIMEZONE'])
    return datetime.datetime.now(beijing_tz)

def format_beijing_time(dt=None, format_str='%Y-%m-%d %H:%M:%S'):
    """格式化北京时间为字符串"""
    if dt is None:
        dt = get_beijing_time()
    elif dt.tzinfo is None:
        # 如果是naive datetime，假设为UTC时间
        dt = pytz.utc.localize(dt)
    
    beijing_tz = pytz.timezone(app.config['TIMEZONE'])
    beijing_dt = dt.astimezone(beijing_tz)
    return beijing_dt.strftime(format_str)

def parse_beijing_time(time_str, format_str='%Y-%m-%d %H:%M:%S'):
    """解析时间字符串为北京时间的datetime对象"""
    beijing_tz = pytz.timezone(app.config['TIMEZONE'])
    naive_dt = datetime.datetime.strptime(time_str, format_str)
    return beijing_tz.localize(naive_dt)

# 验证码相关函数
def generate_captcha():
    """生成验证码"""
    # 生成4位随机字符（数字和字母）
    captcha_text = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    
    # 创建图片
    width, height = 120, 40
    image = Image.new('RGB', (width, height), color='white')
    
    # 添加文字
    from PIL import ImageDraw, ImageFont
    draw = ImageDraw.Draw(image)
    
    # 尝试使用系统字体，如果失败则使用默认字体
    try:
        font = ImageFont.truetype("arial.ttf", 20)
    except:
        font = ImageFont.load_default()
    
    # 绘制文字
    text_width = draw.textlength(captcha_text, font=font)
    text_height = 20
    x = (width - text_width) // 2
    y = (height - text_height) // 2
    
    # 添加一些干扰线
    for _ in range(3):
        x1 = random.randint(0, width)
        y1 = random.randint(0, height)
        x2 = random.randint(0, width)
        y2 = random.randint(0, height)
        draw.line([(x1, y1), (x2, y2)], fill='lightgray', width=1)
    
    # 绘制验证码文字
    draw.text((x, y), captcha_text, fill='black', font=font)
    
    # 添加一些噪点
    for _ in range(50):
        x = random.randint(0, width)
        y = random.randint(0, height)
        draw.point((x, y), fill='lightgray')
    
    # 将图片转换为base64
    buffer = BytesIO()
    image.save(buffer, format='PNG')
    buffer.seek(0)
    image_base64 = base64.b64encode(buffer.getvalue()).decode()
    
    # 将验证码文本存储到session中
    session['captcha'] = captcha_text.lower()
    
    return image_base64

def verify_captcha(user_input):
    """验证验证码"""
    if 'captcha' not in session:
        return False
    
    stored_captcha = session.get('captcha', '').lower()
    user_captcha = user_input.lower().strip()
    
    # 验证后清除session中的验证码
    session.pop('captcha', None)
    
    return stored_captcha == user_captcha

# 添加测试用户
try:
     #检查是否已有超级管理员账号
    conn = db.get_db_connection()
    super_admin = conn.execute('SELECT * FROM users WHERE username = ?', ('fyfy001',)).fetchone()
    conn.close()
    
    if not super_admin:
        db.register_user('fyfy001', 'qinazz0127', '13800138000')
        conn = db.get_db_connection()
        conn.execute('UPDATE users SET role = ? WHERE username = ?', ('superadmin', 'fyfy001'))
        conn.commit()
        conn.close()
        print("已创建超级管理员账号: fyfy001 / qinazz0127")
except Exception as e:
    print(f"创建测试用户时出错: {e}")

# 检查foods表是否有category字段，没有则添加
try:
    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(foods)")
    columns = cursor.fetchall()
    has_category = any(col['name'] == 'category' for col in columns)
    
    if not has_category:
        print("向foods表添加category列...")
        conn.execute("ALTER TABLE foods ADD COLUMN category TEXT")
        conn.commit()
        print("category字段添加成功")
    conn.close()
except Exception as e:
    print(f"检查/修改foods表结构时出错: {e}")

# Ensure upload directory exists
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# Helper functions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def save_image(file, resize=True):
    if file and allowed_file(file.filename):
        # Create a secure filename with a random hex to avoid conflicts
        filename = secure_filename(file.filename)
        random_hex = secrets.token_hex(8)
        _, file_extension = os.path.splitext(filename)
        new_filename = random_hex + file_extension
        
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], new_filename)
        file.save(file_path)
        
        # Resize image if needed
        if resize:
            img = Image.open(file_path)
            if img.height > 1200 or img.width > 1200:
                output_size = (1200, 1200)
                img.thumbnail(output_size)
                img.save(file_path)
        
        return new_filename
    return None

def is_admin():
    return session.get('role') in ['admin', 'superadmin']

def is_connoisseur():
    return session.get('role') == 'connoisseur'

def is_superadmin():
    return session.get('role') == 'superadmin'

def login_required(f):
    """登录验证装饰器"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            flash('请先登录', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def get_db_connection():
    conn = sqlite3.connect('instance/rdfz.db')
    conn.row_factory = sqlite3.Row
    return conn

def get_food_by_id(food_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # 获取食品基本信息
        cursor.execute('''
            SELECT f.*, fl.name as floor_name
            FROM foods f
            JOIN floors fl ON f.floor_id = fl.id
            WHERE f.id = ?
        ''', (food_id,))
        
        food = cursor.fetchone()
        
        if not food:
            return None
        
        # 转换为字典并确保cover_image字段存在
        food_dict = dict(food)
        
        # 获取食品评论
        cursor.execute('''
            SELECT r.*, u.username, u.role
            FROM reviews r
            JOIN users u ON r.user_id = u.id
            WHERE r.food_id = ?
            ORDER BY r.created_at DESC
        ''', (food_id,))
        
        reviews = cursor.fetchall()
        food_dict['reviews'] = [dict(review) for review in reviews]
        
        # 获取食品图片
        cursor.execute('SELECT * FROM images WHERE food_id = ? ORDER BY is_cover DESC', (food_id,))
        images = cursor.fetchall()
        food_dict['images'] = [dict(image) for image in images]
        
        # 计算平均评分
        if reviews:
            total_rating = sum(review['rating'] for review in reviews)
            food_dict['avg_rating'] = total_rating / len(reviews)
        else:
            food_dict['avg_rating'] = 5.0  # 无评论时默认为5星
        
        # 确保cover_image是字符串类型
        cover_image = food_dict.get('cover_image')
        
        # 如果cover_image为None或空字符串，尝试从images表找出is_cover=1的图片
        if not cover_image and images:
            for image in images:
                if image['is_cover'] == 1:
                    food_dict['cover_image'] = image['filename']
                    break
            else:
                # 如果没有标记为封面的图片，使用第一张图片
                if images:
                    food_dict['cover_image'] = images[0]['filename']
        
        print(f"食品ID={food_id}的封面图片是: {food_dict.get('cover_image')}")
        
        return food_dict
    except sqlite3.Error as e:
        print(f"获取食品信息时出错: {e}")
        return None
    finally:
        conn.close()

# Authentication routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        captcha = request.form.get('captcha')
        
        # 验证验证码
        if not verify_captcha(captcha):
            flash('验证码错误', 'error')
            return render_template('login.html')
        
        user = db.authenticate_user(username, password)
        if user:
            session['logged_in'] = True
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            flash('登录成功', 'success')
            return redirect(url_for('index'))
        else:
            flash('用户名或密码错误', 'error')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        phone = request.form.get('phone')
        captcha = request.form.get('captcha')
        
        if not username or not password or not phone:
            flash('请填写所有必填字段', 'error')
            return render_template('register.html')
        
        # 验证验证码
        if not verify_captcha(captcha):
            flash('验证码错误', 'error')
            return render_template('register.html')
        
        if password != confirm_password:
            flash('两次密码输入不一致', 'error')
            return render_template('register.html')
        
        user_id = db.register_user(username, password, phone)
        if user_id:
            flash('注册成功！请登录', 'success')
            return redirect(url_for('login'))
        else:
            flash('用户名已存在', 'error')
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('已退出登录', 'info')
    return redirect(url_for('index'))

# Main routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/captcha')
def get_captcha():
    """获取验证码图片"""
    captcha_image = generate_captcha()
    return jsonify({'captcha': captcha_image})

@app.route('/about_rdfz')
def about_rdfz():
    return redirect('https://www.rdfz.cn')

@app.route('/about_team')
def about_team():
    return render_template('about_team.html')

@app.route('/feedback', methods=['GET', 'POST'])
def feedback():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        message = request.form.get('message')
        
        if not message:
            flash('请填写反馈内容', 'error')
            return render_template('feedback.html')
        
        user_id = session.get('user_id')
        db.add_feedback(name, email, message, user_id)
        
        flash('感谢您的反馈！', 'success')
        return redirect(url_for('index'))
    
    return render_template('feedback.html')

@app.route('/start')
def start():
    if 'user_id' not in session:
        flash('请先登录后再开始探索', 'warning')
        return redirect(url_for('login'))
    return render_template('floors.html')

@app.route('/floor/<int:floor_id>')
def floor(floor_id):
    # 获取楼层信息
    floor = db.get_floor_by_id(floor_id)
    if not floor:
        flash('楼层不存在', 'error')
        return redirect(url_for('start'))
        
    # 获取该楼层的食物列表
    foods = db.get_food_by_floor(floor_id)
    
    return render_template('floor.html', floor=floor, foods=foods)

@app.route('/floor/<int:floor_id>/<meal_time>')
def floor_meal(floor_id, meal_time):
    if meal_time not in ['breakfast', 'lunch', 'dinner']:
        return redirect(url_for('floor', floor_id=floor_id))
    
    # 获取楼层信息
    floor = db.get_floor_by_id(floor_id)
    if not floor:
        flash('楼层不存在', 'error')
        return redirect(url_for('start'))
    
    # 获取该楼层指定餐点的食物列表
    foods = db.get_food_by_floor(floor_id, meal_time)
    
    return render_template('floor.html', floor=floor, foods=foods, meal_time=meal_time)

@app.route('/food/<int:food_id>', methods=['GET', 'POST'])
def food_detail(food_id):
    food = db.get_food_by_id(food_id)
    if not food:
        flash('未找到该菜品', 'error')
        return redirect(url_for('index'))
    
    # 计算平均评分
    if 'reviews' in food and food['reviews']:
        total_rating = sum(review['rating'] for review in food['reviews'] if 'rating' in review)
        avg_rating = total_rating / len(food['reviews']) if food['reviews'] else 0
        food['avg_rating'] = avg_rating
    else:
        food['avg_rating'] = 5.0  # 无评论时默认为5星
    
    # 确保cover_image是可用的字符串
    if food.get('cover_image') is None:
        food['cover_image'] = ''
    elif isinstance(food['cover_image'], dict) and 'filename' in food['cover_image']:
        food['cover_image'] = food['cover_image']['filename']
    
    return render_template('food_detail.html', food=food)

@app.route('/my_reviews')
def my_reviews():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    user_id = session.get('user_id')
    reviews = db.get_user_reviews(user_id)
    
    return render_template('my_reviews.html', reviews=reviews)

@app.route('/profile')
def profile():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    user_id = session.get('user_id')
    user = db.get_user_by_id(user_id)
    
    return render_template('profile.html', user=user)

# Admin routes
@app.route('/admin')
def admin_dashboard():
    if not is_admin():
        flash('需要管理员权限', 'error')
        return redirect(url_for('index'))
    
    return render_template('admin/dashboard.html')

@app.route('/admin/foods', methods=['GET', 'POST'])
def admin_foods():
    if not is_admin():
        flash('需要管理员权限', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        floor_id = request.form.get('floor_id')
        meal_time = request.form.get('meal_time')
        price = request.form.get('price')
        category = request.form.get('category')
        
        if not name or not floor_id:
            flash('请填写必填字段', 'error')
        else:
            user_id = session.get('user_id')
            try:
                # 转换价格为浮点数，如果提供了价格
                price_value = float(price) if price else 0.0
                food_id = db.add_food_item(name, description, floor_id, meal_time, user_id, price_value, category)
                
                # Handle cover image upload
                if 'cover_image' in request.files:
                    file = request.files['cover_image']
                    if file.filename:
                        if file.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                            filename = save_image(file)
                            if filename:
                                db.add_image(food_id, user_id, filename, is_cover=True)
                        else:
                            flash('只允许上传 PNG 或 JPG 文件', 'error')
                
                flash('菜品已添加', 'success')
            except ValueError:
                flash('价格格式不正确', 'error')
            except Exception as e:
                flash(f'添加菜品失败: {str(e)}', 'error')
                
            return redirect(url_for('admin_foods'))
    
    # Get all food items
    floors = db.get_all_floors()
    
    all_foods = []
    for floor in floors:
        foods = db.get_food_by_floor(floor['id'])
        for food in foods:
            food['floor_name'] = floor['name']
            all_foods.append(food)
    
    return render_template('admin/foods.html', floors=floors, foods=all_foods)

@app.route('/admin/foods/edit/<int:food_id>', methods=['GET', 'POST'])
def admin_edit_food(food_id):
    if not (is_admin() or is_connoisseur()):
        flash('需要管理员或美食鉴赏家权限', 'error')
        return redirect(url_for('index'))
    
    food = get_food_by_id(food_id)
    if not food:
        flash('未找到该菜品', 'error')
        return redirect(url_for('admin_foods'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        floor_id = request.form.get('floor_id')
        meal_time = request.form.get('meal_time')
        description = request.form.get('description')
        price = request.form.get('price')
        category = request.form.get('category')
        
        success = False
        
        # 如果是美食鉴赏家，只更新描述
        if is_connoisseur():
            try:
                success = db.update_food_item(food_id, food['name'], description, food['floor_id'], food['meal_time'], food['price'], food.get('category'))
                if success:
                    flash('食品描述更新成功', 'success')
                else:
                    flash('食品描述更新失败', 'error')
            except Exception as e:
                flash(f'更新失败: {str(e)}', 'error')
        else:
            # 管理员可以更新所有信息
            if name and floor_id:
                try:
                    if price:
                        success = db.update_food_item(food_id, name, description, floor_id, meal_time, float(price), category)
                    else:
                        success = db.update_food_item(food_id, name, description, floor_id, meal_time, None, category)
                    
                    if success:
                        flash('食品信息更新成功', 'success')
                    else:
                        flash('食品信息更新失败', 'error')
                except ValueError:
                    flash('价格格式不正确', 'error')
            else:
                flash('请填写必要的信息', 'error')
                return redirect(url_for('admin_edit_food', food_id=food_id))
        
        # 处理封面图片上传（对所有角色都可用）
        cover_image = request.files.get('cover_image')
        if cover_image and cover_image.filename:
            if cover_image.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                filename = save_image(cover_image)
                if filename:
                    user_id = session.get('user_id')
                    
                    # 处理封面图片更新
                    try:
                        # 先添加到images表
                        db.add_image(food_id, user_id, filename, is_cover=True)
                        
                        # 然后更新foods表
                        conn = db.get_db_connection()
                        conn.execute('UPDATE foods SET cover_image = ? WHERE id = ?', (filename, food_id))
                        conn.commit()
                        conn.close()
                        
                        flash('封面图片已更新', 'success')
                    except sqlite3.Error as e:
                        flash(f'封面图片更新失败: {e}', 'error')
                else:
                    flash('封面图片上传失败', 'error')
        
        return redirect(url_for('admin_edit_food', food_id=food_id))
    
    floors = db.get_all_floors()
    return render_template('admin/edit_food.html', food=food, floors=floors)

@app.route('/admin/set_cover/<int:food_id>/<int:image_id>', methods=['POST'])
def admin_set_cover(food_id, image_id):
    if not is_admin():
        flash('需要管理员权限', 'error')
        return redirect(url_for('index'))
    
    print(f"\n====== 开始设置图片ID={image_id}为封面 ======")
    conn = None
    
    try:
        # 直接连接数据库，确保获取最新数据
        conn = sqlite3.connect('instance/rdfz.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 验证图片存在
        cursor.execute('SELECT * FROM images WHERE id = ?', (image_id,))
        image = cursor.fetchone()
        if not image:
            print(f"错误: 图片ID={image_id}不存在")
            flash('图片不存在', 'error')
            return redirect(url_for('admin_edit_food', food_id=food_id))
        
        # 验证图片属于该食品
        if image['food_id'] != food_id:
            print(f"错误: 图片ID={image_id}不属于食品ID={food_id}")
            flash('图片不属于该食品', 'error')
            return redirect(url_for('admin_edit_food', food_id=food_id))
        
        filename = image['filename']
        print(f"图片信息: filename={filename}, food_id={food_id}")
        
        # 开始事务
        cursor.execute('BEGIN TRANSACTION')
        
        # 1. 清除该食品所有图片的封面标志
        cursor.execute('UPDATE images SET is_cover = 0 WHERE food_id = ?', (food_id,))
        print(f"已重置食品ID={food_id}的所有图片封面标志")
        
        # 2. 设置当前图片为封面
        cursor.execute('UPDATE images SET is_cover = 1 WHERE id = ?', (image_id,))
        print(f"已将图片ID={image_id}设为封面")
        
        # 3. 关键步骤：更新foods表的cover_image字段
        cursor.execute('UPDATE foods SET cover_image = ? WHERE id = ?', (filename, food_id))
        rows_affected = cursor.rowcount
        print(f"更新foods表封面字段: 影响了{rows_affected}行, 新封面={filename}")
        
        # 4. 验证更新是否成功
        cursor.execute('SELECT cover_image FROM foods WHERE id = ?', (food_id,))
        updated_food = cursor.fetchone()
        if updated_food and updated_food['cover_image'] == filename:
            print(f"验证成功: 食品ID={food_id}的封面已更新为{filename}")
        else:
            print(f"警告: 封面可能未正确更新。数据库显示为: {updated_food['cover_image'] if updated_food else 'None'}")
        
        # 提交事务
        conn.commit()
        print("数据库事务已提交")
        
        # 发送成功消息
        flash('封面图片已成功更新！', 'success')
        
    except sqlite3.Error as e:
        print(f"数据库错误: {e}")
        flash(f'设置封面失败: {e}', 'error')
        if conn:
            try:
                conn.rollback()
                print("事务已回滚")
            except:
                pass
    except Exception as e:
        print(f"意外错误: {e}")
        flash(f'设置封面失败: {e}', 'error')
        if conn:
            try:
                conn.rollback()
            except:
                pass
    finally:
        if conn:
            conn.close()
            print("数据库连接已关闭")
    
    print("====== 设置封面操作完成 ======\n")
    
    # 添加时间戳以确保刷新
    return redirect(url_for('admin_edit_food', food_id=food_id, t=int(time.time())))

@app.route('/admin/delete_image/<int:image_id>', methods=['POST'])
def admin_delete_image(image_id):
    if not is_admin():
        flash('需要管理员权限', 'error')
        return redirect(url_for('index'))
    
    print(f"\n==== 删除图片 ID={image_id} ====")
    try:
        # 获取图片信息
        conn = sqlite3.connect('instance/rdfz.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 1. 获取图片信息
        cursor.execute('SELECT * FROM images WHERE id = ?', (image_id,))
        image = cursor.fetchone()
        
        if not image:
            print(f"错误: 未找到图片 ID={image_id}")
            flash('未找到该图片', 'error')
            return redirect(url_for('admin_foods'))
        
        food_id = image['food_id']
        filename = image['filename']
        is_cover = image['is_cover']
        
        print(f"图片信息: food_id={food_id}, filename={filename}, is_cover={is_cover}")
        
        # 2. 检查这是否是food表中的cover_image
        cursor.execute('SELECT cover_image FROM foods WHERE id = ?', (food_id,))
        food = cursor.fetchone()
        is_food_cover = (food and food['cover_image'] == filename)
        print(f"是否是food表中的cover_image: {is_food_cover}")
        
        # 3. 检查剩余图片数量(不包括要删除的这张)
        cursor.execute('SELECT COUNT(*) as count FROM images WHERE food_id = ? AND id != ?', (food_id, image_id))
        remaining_count = cursor.fetchone()['count']
        print(f"剩余图片数量: {remaining_count}")
        
        # 4. 开始事务
        cursor.execute('BEGIN TRANSACTION')
        
        # 5. 首先处理foods表的cover_image字段
        if is_food_cover or remaining_count == 0:
            # 如果删除的是封面图片或者是最后一张图片
            if remaining_count > 0:
                # 如果还有其他图片，设置新的封面
                cursor.execute('''
                    SELECT id, filename FROM images 
                    WHERE food_id = ? AND id != ?
                    ORDER BY created_at DESC 
                    LIMIT 1
                ''', (food_id, image_id))
                next_image = cursor.fetchone()
                
                # 更新foods表的cover_image
                cursor.execute('UPDATE foods SET cover_image = ? WHERE id = ?', 
                               (next_image['filename'], food_id))
                print(f"设置新的封面图片: {next_image['filename']}")
                
                # 更新images表的is_cover标记
                cursor.execute('UPDATE images SET is_cover = 0 WHERE food_id = ?', (food_id,))
                cursor.execute('UPDATE images SET is_cover = 1 WHERE id = ?', (next_image['id'],))
            else:
                # 如果没有剩余图片，清除封面
                cursor.execute('UPDATE foods SET cover_image = NULL WHERE id = ?', (food_id,))
                print(f"清除封面图片(没有剩余图片)")
        
        # 6. 删除图片记录
        cursor.execute('DELETE FROM images WHERE id = ?', (image_id,))
        deleted_count = cursor.rowcount
        print(f"已删除图片记录: {deleted_count}行")
        
        # 7. 提交事务
        cursor.execute('COMMIT')
        print("事务已提交")
        conn.close()
        
        # 8. 从磁盘删除文件
        try:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"已从磁盘删除文件: {file_path}")
            else:
                print(f"文件不存在于磁盘: {file_path}")
        except Exception as e:
            print(f"删除文件时出错: {e}")
        
        flash('图片已删除', 'success')
        print("==== 图片删除成功 ====\n")
        
        # 9. 重定向回编辑页面
        return redirect(url_for('admin_edit_food', food_id=food_id))
        
    except sqlite3.Error as e:
        print(f"数据库错误: {e}")
        try:
            # 回滚事务
            cursor.execute('ROLLBACK')
            print("已回滚事务")
        except:
            pass
        finally:
            if conn:
                conn.close()
        
        flash('删除图片失败: 数据库错误', 'error')
        return redirect(url_for('admin_foods'))
    except Exception as e:
        print(f"未知错误: {e}")
        flash('删除图片失败: 未知错误', 'error')
        return redirect(url_for('admin_foods'))

@app.route('/admin/delete_review/<int:review_id>', methods=['POST'])
def admin_delete_review(review_id):
    if not is_admin():
        flash('需要管理员权限', 'error')
        return redirect(url_for('index'))
    
    # Get the food_id before deleting the review
    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT food_id FROM reviews WHERE id = ?', (review_id,))
    result = cursor.fetchone()
    conn.close()
    
    if result:
        food_id = result['food_id']
        db.delete_review(review_id, is_admin=True)
        flash('评论已删除', 'success')
        return redirect(url_for('food_detail', food_id=food_id))
    
    flash('未找到该评论', 'error')
    return redirect(url_for('admin_foods'))

# Super admin routes
@app.route('/admin/users')
def admin_users():
    if not is_superadmin():
        flash('需要超级管理员权限', 'error')
        return redirect(url_for('index'))
    
    # 获取排序参数
    sort_by = request.args.get('sort', 'username')  # 默认按用户名排序
    order = request.args.get('order', 'asc')  # 默认升序
    
    users = db.get_all_users(sort_by=sort_by, order=order)
    
    # 格式化注册时间为北京时间
    for user in users:
        if user.get('created_at'):
            try:
                # 解析数据库中的时间并转换为北京时间
                dt = datetime.datetime.strptime(user['created_at'], '%Y-%m-%d %H:%M:%S')
                user['created_at'] = format_beijing_time(dt)
            except:
                pass  # 如果时间格式不正确，保持原样
    
    return render_template('admin/users.html', users=users, sort_by=sort_by, order=order)

@app.route('/admin/change_role/<int:user_id>', methods=['POST'])
def admin_change_role(user_id):
    if not is_superadmin():
        flash('需要超级管理员权限', 'error')
        return redirect(url_for('index'))
    
    role = request.form.get('role')
    if role not in ['user', 'admin', 'superadmin', 'connoisseur']:
        flash('无效的角色', 'error')
        return redirect(url_for('admin_users'))
    
    db.update_user_role(user_id, role)
    flash('用户角色已更新', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
def admin_delete_user(user_id):
    if not is_superadmin():
        flash('需要超级管理员权限', 'error')
        return redirect(url_for('index'))
    
    if db.delete_user(user_id):
        flash('用户已删除', 'success')
    else:
        flash('无法删除该用户', 'error')
    
    return redirect(url_for('admin_users'))

@app.route('/admin/feedback')
def admin_feedback():
    if not is_superadmin():
        flash('需要超级管理员权限', 'error')
        return redirect(url_for('index'))
    
    include_read = request.args.get('include_read') == 'true'
    feedback = db.get_all_feedback(include_read)
    
    return render_template('admin/feedback.html', feedback=feedback, include_read=include_read)

@app.route('/admin/respond_feedback/<int:feedback_id>', methods=['POST'])
def admin_respond_feedback(feedback_id):
    if not is_superadmin():
        flash('需要超级管理员权限', 'error')
        return redirect(url_for('index'))
    
    response = request.form.get('response')
    
    if response:
        db.respond_to_feedback(feedback_id, response)
        flash('回复已发送', 'success')
    else:
        flash('请填写回复内容', 'error')
    
    return redirect(url_for('admin_feedback'))

# API routes for AJAX
@app.route('/api/delete_review/<int:review_id>', methods=['POST'])
def api_delete_review(review_id):
    if not session.get('logged_in'):
        return jsonify({'success': False, 'message': '需要登录'}), 401
    
    user_id = session.get('user_id')
    role = session.get('role')
    
    try:
        # 获取评论信息
        conn = db.get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM reviews WHERE id = ?', (review_id,))
        review = cursor.fetchone()
        conn.close()
        
        if not review:
            print(f"评论不存在: ID={review_id}")
            return jsonify({'success': False, 'message': '评论不存在'}), 404
        
        # 检查权限：超级管理员可以删除任何评论，用户只能删除自己的评论
        if role == 'superadmin' or review['user_id'] == user_id:
            # 调用数据库函数删除评论
            is_admin = role in ['admin', 'superadmin']
            
            print(f"尝试删除评论: review_id={review_id}, user_id={user_id}, is_admin={is_admin}")
            result = db.delete_review(review_id, user_id, is_admin)
            print(f"删除评论结果: {result}")
            
            if result:
                return jsonify({'success': True})
            else:
                return jsonify({'success': False, 'message': '删除操作失败'}), 500
        else:
            print(f"无权删除: user_id={user_id}, review_user_id={review['user_id']}, role={role}")
            return jsonify({'success': False, 'message': '无权删除该评论'}), 403
    except Exception as e:
        print(f"删除评论时出错: {str(e)}")
        return jsonify({'success': False, 'message': f'服务器错误: {str(e)}'}), 500

@app.route('/api/zoom_effect')
def api_zoom_effect():
    # Simulate a delay for the zoom effect
    time.sleep(0.5)
    return jsonify({'success': True})

@app.route('/food/<int:food_id>/review', methods=['POST'])
def add_review(food_id):
    # 评论提交逻辑
    if not session.get('logged_in'):
        flash('请先登录再评论', 'error')
        return redirect(url_for('login', next=url_for('food_detail', food_id=food_id)))
    
    user_id = session.get('user_id')
    rating = request.form.get('rating')
    comment = request.form.get('comment')
    image = request.files.get('image')
    
    if not rating:
        flash('请选择评分', 'error')
        return redirect(url_for('food_detail', food_id=food_id))
    
    try:
        filename = None
        if image and image.filename:
            if image.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                filename = save_image(image)
            else:
                flash('只允许上传 PNG 或 JPG 文件', 'error')
        
        success = db.add_review(food_id, user_id, int(rating), comment)
        
        if success:
            flash('评论提交成功', 'success')
        else:
            flash('评论提交失败', 'error')
    except Exception as e:
        flash(f'评论提交出错: {str(e)}', 'error')
    
    return redirect(url_for('food_detail', food_id=food_id))

def check_cover_image_consistency():
    conn = sqlite3.connect('instance/rdfz.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT id, cover_image FROM foods')
    foods = cursor.fetchall()
    
    for food in foods:
        food_id = food['id']
        cover_image = food['cover_image']
        
        # 查找该食品的所有封面图片
        cursor.execute('SELECT id, filename FROM images WHERE food_id = ? AND is_cover = 1', (food_id,))
        cover_images = cursor.fetchall()
        
        if cover_image and not cover_images:
            # 食品有封面但images表没有对应记录
            print(f"食品ID={food_id}有封面图片但没有对应的images记录，修复中...")
            cursor.execute('UPDATE images SET is_cover = 1 WHERE food_id = ? AND filename = ? LIMIT 1', 
                          (food_id, cover_image))
        elif cover_images and cover_image != cover_images[0]['filename']:
            # images表中的封面与foods表不一致
            print(f"食品ID={food_id}的封面图片不一致，修复中...")
            cursor.execute('UPDATE foods SET cover_image = ? WHERE id = ?', 
                          (cover_images[0]['filename'], food_id))
    
    conn.commit()
    conn.close()
    

def fix_cover_image_inconsistencies():
    
    
    conn = sqlite3.connect('instance/rdfz.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # 修复1：将所有food_id相同的图片中最多只有一个is_cover=1
        cursor.execute('''
            SELECT food_id, COUNT(*) as cover_count
            FROM images 
            WHERE is_cover = 1 
            GROUP BY food_id 
            HAVING cover_count > 1
        ''')
        multiple_covers = cursor.fetchall()
        
        for item in multiple_covers:
            food_id = item['food_id']
            print(f"修复: 食品ID={food_id}有多个封面图片")
            
            # 获取该食品所有标记为封面的图片，按时间降序排序
            cursor.execute('''
                SELECT id FROM images 
                WHERE food_id = ? AND is_cover = 1 
                ORDER BY created_at DESC
            ''', (food_id,))
            
            cover_images = cursor.fetchall()
            
            # 保留最新的一个，其余重置为非封面
            for i, img in enumerate(cover_images):
                if i > 0:  # 跳过第一个（最新的）
                    cursor.execute('UPDATE images SET is_cover = 0 WHERE id = ?', (img['id'],))
            
            print(f"已将食品ID={food_id}的多个封面减少为一个")
        
        # 修复2：确保foods表的cover_image与images表的is_cover=1一致
        cursor.execute('SELECT id, cover_image FROM foods')
        foods = cursor.fetchall()
        
        for food in foods:
            food_id = food['id']
            cover_image = food['cover_image']
            
            # 获取标记为封面的图片
            cursor.execute('SELECT id, filename FROM images WHERE food_id = ? AND is_cover = 1', (food_id,))
            cover_in_images = cursor.fetchone()
            
            if cover_image and not cover_in_images:
                # foods有封面但images没有对应记录
                print(f"修复: 食品ID={food_id}的foods表有封面但images表无对应记录")
                
                # 查找该文件名的图片并设为封面
                cursor.execute('SELECT id FROM images WHERE food_id = ? AND filename = ?', 
                              (food_id, cover_image))
                matching_image = cursor.fetchone()
                
                if matching_image:
                    cursor.execute('UPDATE images SET is_cover = 1 WHERE id = ?', (matching_image['id'],))
                    print(f"已将图片ID={matching_image['id']}设为封面")
                else:
                    # 如果没找到对应文件名的图片，使用第一张图片
                    cursor.execute('SELECT id, filename FROM images WHERE food_id = ? LIMIT 1', (food_id,))
                    first_image = cursor.fetchone()
                    
                    if first_image:
                        cursor.execute('UPDATE images SET is_cover = 1 WHERE id = ?', (first_image['id'],))
                        cursor.execute('UPDATE foods SET cover_image = ? WHERE id = ?', 
                                      (first_image['filename'], food_id))
                        print(f"已将图片ID={first_image['id']}设为封面并更新foods表")
                    else:
                        # 没有图片，清除foods表的封面
                        cursor.execute('UPDATE foods SET cover_image = NULL WHERE id = ?', (food_id,))
                        print(f"已清除食品ID={food_id}的封面（无图片）")
            
            elif not cover_image and cover_in_images:
                # images有封面但foods没有对应记录
                print(f"修复: 食品ID={food_id}的images表有封面但foods表无对应记录")
                cursor.execute('UPDATE foods SET cover_image = ? WHERE id = ?', 
                              (cover_in_images['filename'], food_id))
                print(f"已更新foods表的封面为{cover_in_images['filename']}")
            
            elif cover_image and cover_in_images and cover_image != cover_in_images['filename']:
                # foods和images的封面不一致
                print(f"修复: 食品ID={food_id}的foods表和images表封面不一致")
                # 以images表为准
                cursor.execute('UPDATE foods SET cover_image = ? WHERE id = ?', 
                              (cover_in_images['filename'], food_id))
                print(f"已更新foods表的封面为{cover_in_images['filename']}")
        
        conn.commit()
        
    except sqlite3.Error as e:
        conn.rollback()
        print(f"修复过程中出错: {e}")
    finally:
        conn.close()

# 在应用初始化时调用修复函数
with app.app_context():
    check_cover_image_consistency()
    fix_cover_image_inconsistencies()

@app.route('/debug/check_cover_images')
def debug_check_cover_images():
    if not is_admin():
        flash('需要管理员权限', 'error')
        return redirect(url_for('index'))
    
    results = []
    conn = sqlite3.connect('instance/rdfz.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 获取所有食品
    cursor.execute('SELECT id, name, cover_image FROM foods')
    foods = cursor.fetchall()
    
    for food in foods:
        food_id = food['id']
        food_name = food['name']
        cover_image = food['cover_image']
        
        # 检查images表中标记为封面的图片
        cursor.execute('SELECT id, filename FROM images WHERE food_id = ? AND is_cover = 1', (food_id,))
        cover_images = cursor.fetchall()
        
        # 收集诊断信息
        result = {
            'food_id': food_id,
            'food_name': food_name,
            'foods_cover': cover_image,
            'images_cover': [dict(img) for img in cover_images],
            'status': 'OK'
        }
        
        # 检查是否一致
        if not cover_image and not cover_images:
            result['status'] = '无封面图片'
        elif cover_image and not cover_images:
            result['status'] = '错误：foods表有封面但images表无对应记录'
        elif not cover_image and cover_images:
            result['status'] = '错误：images表有封面但foods表无对应记录'
        elif len(cover_images) > 1:
            result['status'] = '错误：多个图片被标记为封面'
        elif cover_image != cover_images[0]['filename']:
            result['status'] = '错误：foods表和images表的封面不一致'
        
        results.append(result)
    
    conn.close()
    
    # 返回HTML格式的诊断结果
    html = '<h1>封面图片诊断结果</h1><table border="1">'
    html += '<tr><th>食品ID</th><th>名称</th><th>foods表封面</th><th>images表封面</th><th>状态</th></tr>'
    
    for result in results:
        html += f'<tr>'
        html += f'<td>{result["food_id"]}</td>'
        html += f'<td>{result["food_name"]}</td>'
        html += f'<td>{result["foods_cover"] or "无"}</td>'
        html += f'<td>{", ".join(img["filename"] for img in result["images_cover"]) if result["images_cover"] else "无"}</td>'
        html += f'<td>{result["status"]}</td>'
        html += f'</tr>'
    
    html += '</table>'
    html += '<p><a href="/admin/foods">返回食品管理</a></p>'
    
    return html

@app.route('/admin/delete_food/<int:food_id>', methods=['POST'])
def admin_delete_food(food_id):
    if not is_admin():
        flash('需要管理员权限', 'error')
        return redirect(url_for('index'))
    
    # 在这里添加删除食品的逻辑
    success = db.delete_food_item(food_id)  # 假设您有一个函数来删除食品
    if success:
        flash('食品已删除', 'success')
    else:
        flash('删除食品失败', 'error')
    
    return redirect(url_for('admin_foods'))

@app.route('/search')
def search():
    # 检查用户是否已登录
    if not session.get('logged_in'):
        flash('请先登录后再搜索', 'warning')
        return redirect(url_for('login'))
        
    q = request.args.get('q', '')
    if not q:
        return redirect(url_for('index'))
    
    # 获取所有楼层
    floors = db.get_all_floors()
    
    # 从数据库获取符合搜索条件的食品
    conn = db.get_db_connection()
    cursor = conn.cursor()
    
    # 构建SQL查询语句，搜索名称和描述中包含关键词的美食
    query = '''
        SELECT f.*, fl.name as floor_name, fl.description as floor_description,
               (SELECT AVG(rating) FROM reviews WHERE food_id = f.id) as avg_rating,
               f.cover_image
        FROM foods f
        JOIN floors fl ON f.floor_id = fl.id
        WHERE f.name LIKE ? 
           OR f.description LIKE ?
           OR fl.name LIKE ?
           OR fl.description LIKE ?
           OR (
              f.meal_time = 'breakfast' AND ? LIKE '%早餐%'
           ) 
           OR (
              f.meal_time = 'lunch' AND ? LIKE '%午餐%'
           )
           OR (
              f.meal_time = 'dinner' AND ? LIKE '%晚餐%'
           )
           OR (
              f.category LIKE ?
           )
        ORDER BY avg_rating DESC
    '''
    
    cursor.execute(query, (f'%{q}%', f'%{q}%', f'%{q}%', f'%{q}%', q, q, q, f'%{q}%'))
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
    
    conn.close()
    
    return render_template('search_results.html', q=q, foods=foods, floors=floors)

@app.route('/rankings')
def rankings():
    # 检查用户是否已登录
    if not session.get('logged_in'):
        flash('请先登录后再查看排行榜', 'warning')
        return redirect(url_for('login'))
    
    # 获取排序类型参数，默认为热度排行
    sort_type = request.args.get('type', 'hot')
    
    conn = db.get_db_connection()
    cursor = conn.cursor()
    
    if sort_type == 'hot':
        # 按热度排行：评论数越多越靠前
        query = '''
            SELECT f.*, fl.name as floor_name,
                   COUNT(r.id) as review_count,
                   AVG(r.rating) as avg_rating,
                   f.cover_image
            FROM foods f
            JOIN floors fl ON f.floor_id = fl.id
            LEFT JOIN reviews r ON f.id = r.food_id
            GROUP BY f.id
            ORDER BY review_count DESC, avg_rating DESC
            LIMIT 50
        '''
        title = "热度排行榜"
        subtitle = "按评论数量排序"
        foods = [dict(food) for food in cursor.execute(query).fetchall()]
        
        # 处理食品数据
        for i, food in enumerate(foods):
            food['rank'] = i + 1
            food['avg_rating'] = round(food['avg_rating'], 1) if food['avg_rating'] else 0.0
            
            # 处理封面图片
            if food['cover_image'] is None:
                cursor.execute('''
                    SELECT filename FROM images 
                    WHERE food_id = ? AND is_cover = 1 
                    LIMIT 1
                ''', (food['id'],))
                cover = cursor.fetchone()
                if cover:
                    food['cover_image'] = cover['filename']
        
        conn.close()
        return render_template('rankings.html', 
                             foods=foods, 
                             sort_type=sort_type, 
                             title=title,
                             subtitle=subtitle)
    
    elif sort_type == 'score':
        # 按得分排行：评论数 * 平均得分
        query = '''
            SELECT f.*, fl.name as floor_name,
                   COUNT(r.id) as review_count,
                   AVG(r.rating) as avg_rating,
                   (COUNT(r.id) * AVG(r.rating)) as score,
                   f.cover_image
            FROM foods f
            JOIN floors fl ON f.floor_id = fl.id
            LEFT JOIN reviews r ON f.id = r.food_id
            GROUP BY f.id
            HAVING review_count > 0
            ORDER BY score DESC, avg_rating DESC
            LIMIT 50
        '''
        title = "得分排行榜"
        subtitle = "按评论数×平均得分排序"
        foods = [dict(food) for food in cursor.execute(query).fetchall()]
        
        # 处理食品数据
        for i, food in enumerate(foods):
            food['rank'] = i + 1
            food['avg_rating'] = round(food['avg_rating'], 1) if food['avg_rating'] else 0.0
            food['score'] = round(food.get('score', 0), 1)
            
            # 处理封面图片
            if food['cover_image'] is None:
                cursor.execute('''
                    SELECT filename FROM images 
                    WHERE food_id = ? AND is_cover = 1 
                    LIMIT 1
                ''', (food['id'],))
                cover = cursor.fetchone()
                if cover:
                    food['cover_image'] = cover['filename']
        
        conn.close()
        return render_template('rankings.html', 
                             foods=foods, 
                             sort_type=sort_type, 
                             title=title,
                             subtitle=subtitle)
    
    else:  # users 用户排行
        # 按用户评论数排行
        query = '''
            SELECT u.id, u.username, u.role, u.created_at,
                   COUNT(r.id) as review_count,
                   AVG(r.rating) as avg_rating,
                   MIN(r.created_at) as first_review_date,
                   MAX(r.created_at) as last_review_date
            FROM users u
            LEFT JOIN reviews r ON u.id = r.user_id
            GROUP BY u.id
            HAVING review_count > 0
            ORDER BY review_count DESC, avg_rating DESC
            LIMIT 50
        '''
        title = "鉴赏家排行榜"
        subtitle = "按用户评论数量排序"
        users = [dict(user) for user in cursor.execute(query).fetchall()]
        
        # 处理用户数据
        for i, user in enumerate(users):
            user['rank'] = i + 1
            user['avg_rating'] = round(user['avg_rating'], 1) if user['avg_rating'] else 0.0
            
            # 角色翻译
            role_map = {
                'user': '普通用户',
                'connoisseur': '美食鉴赏家',
                'admin': '管理员',
                'superadmin': '超级管理员'
            }
            user['role_display'] = role_map.get(user['role'], user['role'])
            
            # 计算活跃天数
            if user['first_review_date'] and user['last_review_date']:
                from datetime import datetime
                try:
                    first_date = datetime.strptime(user['first_review_date'], '%Y-%m-%d %H:%M:%S')
                    last_date = datetime.strptime(user['last_review_date'], '%Y-%m-%d %H:%M:%S')
                    user['active_days'] = (last_date - first_date).days + 1
                except:
                    user['active_days'] = 1
            else:
                user['active_days'] = 1
        
        conn.close()
        return render_template('rankings.html', 
                             users=users, 
                             sort_type=sort_type, 
                             title=title,
                             subtitle=subtitle)

# 流量监测中间件 - 已禁用
@app.before_request
def traffic_monitoring():
    """流量监测中间件 - 已禁用"""
    # 功能已禁用
    return

@app.after_request
def log_request(response):
    """记录请求日志 - 已禁用"""
    # 功能已禁用
    return response

# 流量监测页面路由 - 已禁用
@app.route('/admin/traffic')
@login_required
def admin_traffic():
    """流量监测页面 - 已禁用"""
    if not is_superadmin():
        abort(403)
    
    # 功能已禁用
    flash('流量监控功能已被禁用', 'warning')
    return redirect(url_for('admin_dashboard'))

# 确保应用可以被 Gunicorn 找到
application = app

# 添加main函数作为WSGI入口点
def main():
    return application

if __name__ == '__main__':
    # 开发环境下使用 Flask 内置服务器
    app.run(host='0.0.0.0', port=5001, debug=False)

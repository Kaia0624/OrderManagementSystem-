from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, FloatField, TextAreaField, IntegerField, SelectField
from wtforms.validators import DataRequired, Length, EqualTo, NumberRange, ValidationError
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from flask_caching import Cache
from redis import Redis
import json
import threading
from functools import wraps
import time
import logging
from logging.handlers import RotatingFileHandler
from enum import Enum
import re
from decimal import Decimal

# 配置日志系统
logging.basicConfig(
    handlers=[RotatingFileHandler('app.log', maxBytes=100000, backupCount=3)],
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
)

# 订单状态枚举
class OrderStatus(Enum):
    PENDING = '已下单'
    PROCESSING = '准备中'
    COMPLETED = '已完成'
    CANCELLED = '已取消'

# 数据验证装饰器
def validate_data(schema):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                schema.validate(request.form)
            except ValidationError as e:
                logging.error(f"数据验证失败: {str(e)}")
                flash(f"数据验证失败: {str(e)}")
                return redirect(request.referrer)
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# 数据完整性检查装饰器
def check_data_integrity(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            result = f(*args, **kwargs)
            db.session.flush()  # 检查数据库约束
            return result
        except Exception as e:
            db.session.rollback()
            logging.error(f"数据完整性检查失败: {str(e)}")
            flash("操作失败，请检查输入数据")
            return redirect(request.referrer)
    return decorated_function

# 价格验证器
def validate_price(form, field):
    if not isinstance(field.data, (int, float, Decimal)):
        raise ValidationError('价格必须是数字')
    if field.data <= 0:
        raise ValidationError('价格必须大于0')

# 电话号码验证器
def validate_phone(form, field):
    if not re.match(r'^\d{11}$', field.data):
        raise ValidationError('请输入11位有效的电话号码')

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'  # 用于session加密
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ordersystem.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 添加缓存配置
app.config['CACHE_TYPE'] = 'redis'
app.config['CACHE_REDIS_URL'] = 'redis://localhost:6379/0'
cache = Cache(app)
redis_client = Redis(host='localhost', port=6379, db=0)

# 批量处理队列
order_queue = []
BATCH_SIZE = 10
queue_lock = threading.Lock()

def process_order_batch():
    """批量处理订单"""
    global order_queue
    with queue_lock:
        if len(order_queue) >= BATCH_SIZE:
            batch = order_queue[:BATCH_SIZE]
            order_queue = order_queue[BATCH_SIZE:]
            
            # 批量插入订单
            with app.app_context():
                try:
                    db.session.bulk_save_objects(batch)
                    db.session.commit()
                except Exception as e:
                    db.session.rollback()
                    # 处理失败的订单重新加入队列
                    order_queue.extend(batch)
                    print(f"Error processing batch: {str(e)}")

# 启动后台处理线程
def start_background_processing():
    def background_worker():
        while True:
            process_order_batch()
            time.sleep(1)  # 每秒检查一次队列
    
    thread = threading.Thread(target=background_worker, daemon=True)
    thread.start()

# 缓存装饰器
def cache_order(timeout=300):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            cache_key = f"order_{request.view_args.get('id', '')}"
            rv = cache.get(cache_key)
            if rv is not None:
                return rv
            rv = f(*args, **kwargs)
            cache.set(cache_key, rv, timeout=timeout)
            return rv
        return decorated_function
    return decorator

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# 用户模型
class User(UserMixin, db.Model):
    __tablename__ = 'user'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False, index=True)
    password = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20))
    address = db.Column(db.String(100))
    is_admin = db.Column(db.Boolean, default=False)
    orders = db.relationship('Order', backref='user', lazy=True)
    favorites = db.relationship('UserFavorite', backref='user', lazy=True)

# 餐厅模型
class Restaurant(db.Model):
    __tablename__ = 'restaurant'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, index=True)
    address = db.Column(db.String(200))
    phone = db.Column(db.String(20))
    description = db.Column(db.String(500))
    dishes = db.relationship('Dish', backref='restaurant', lazy=True)
    orders = db.relationship('Order', backref='restaurant', lazy=True)
    favorites = db.relationship('UserFavorite', backref='restaurant', lazy=True)

# 菜品模型
class Dish(db.Model):
    __tablename__ = 'dish'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, index=True)
    description = db.Column(db.String(255))
    price = db.Column(db.Float, nullable=False)
    restaurant_id = db.Column(db.Integer, db.ForeignKey('restaurant.id'), nullable=False)
    is_available = db.Column(db.Boolean, default=True)
    order_details = db.relationship('OrderDetail', backref='dish', lazy=True)

# 订单模型
class Order(db.Model):
    __tablename__ = 'order'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    restaurant_id = db.Column(db.Integer, db.ForeignKey('restaurant.id'), nullable=False)
    order_time = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    status = db.Column(db.Enum(OrderStatus), nullable=False, default=OrderStatus.PENDING, index=True)
    total_amount = db.Column(db.DECIMAL(10, 2), nullable=False)
    delivery_address = db.Column(db.String(200))
    note = db.Column(db.String(500))
    order_details = db.relationship('OrderDetail', backref='order', lazy=True)
    
    # 添加复合索引
    __table_args__ = (
        db.Index('idx_user_status', user_id, status),
        db.Index('idx_restaurant_status', restaurant_id, status),
        db.Index('idx_order_time', order_time.desc())
    )
    
    def can_transition_to(self, new_status):
        """检查订单状态转换是否有效"""
        valid_transitions = {
            OrderStatus.PENDING: [OrderStatus.PROCESSING, OrderStatus.CANCELLED],
            OrderStatus.PROCESSING: [OrderStatus.COMPLETED, OrderStatus.CANCELLED],
            OrderStatus.COMPLETED: [],
            OrderStatus.CANCELLED: []
        }
        return new_status in valid_transitions.get(self.status, [])

    def transition_to(self, new_status):
        """转换订单状态"""
        if not self.can_transition_to(new_status):
            raise ValueError(f"不能从 {self.status.value} 转换到 {new_status.value}")
        self.status = new_status
        logging.info(f"订单 {self.id} 状态更新为 {new_status.value}")

# 订单明细模型
class OrderDetail(db.Model):
    __tablename__ = 'order_detail'
    
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    dish_id = db.Column(db.Integer, db.ForeignKey('dish.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.DECIMAL(10, 2), nullable=False)
    subtotal = db.Column(db.DECIMAL(10, 2), nullable=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.unit_price and self.quantity:
            self.subtotal = self.unit_price * self.quantity

# 用户收藏模型
class UserFavorite(db.Model):
    __tablename__ = 'user_favorite'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    restaurant_id = db.Column(db.Integer, db.ForeignKey('restaurant.id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('user_id', 'restaurant_id', name='unique_user_restaurant'),)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# 注册表单
class RegistrationForm(FlaskForm):
    username = StringField('用户名', validators=[DataRequired(), Length(min=4, max=20)])
    password = PasswordField('密码', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('确认密码', validators=[DataRequired(), EqualTo('password')])
    phone = StringField('电话号码', validators=[Length(max=20)])
    address = StringField('地址', validators=[Length(max=100)])
    submit = SubmitField('注册')

# 登录表单
class LoginForm(FlaskForm):
    username = StringField('用户名', validators=[DataRequired()])
    password = PasswordField('密码', validators=[DataRequired()])
    submit = SubmitField('登录')

# 菜品表单
class DishForm(FlaskForm):
    name = StringField('菜品名称', validators=[DataRequired(), Length(min=1, max=100)])
    description = TextAreaField('描述')
    price = FloatField('价格', validators=[DataRequired(), NumberRange(min=0)])
    restaurant_id = SelectField('所属餐厅', coerce=int, validators=[DataRequired()])
    submit = SubmitField('提交')

# 增强的订单表单
class OrderForm(FlaskForm):
    dish_id = SelectField('选择菜品', coerce=int, validators=[DataRequired()])
    quantity = IntegerField('数量', validators=[
        DataRequired(),
        NumberRange(min=1, max=100, message='数量必须在1-100之间')
    ])
    note = TextAreaField('备注', validators=[Length(max=500)])
    submit = SubmitField('添加到订单')

    def validate_dish_id(self, field):
        dish = Dish.query.get(field.data)
        if not dish:
            raise ValidationError('选择的菜品不存在')
        if not dish.is_available:
            raise ValidationError('该菜品已下架')

# 餐厅表单
class RestaurantForm(FlaskForm):
    name = StringField('餐厅名称', validators=[DataRequired(), Length(min=1, max=100)])
    address = StringField('地址', validators=[DataRequired(), Length(max=200)])
    phone = StringField('电话', validators=[DataRequired(), Length(max=20)])
    description = TextAreaField('描述', validators=[Length(max=500)])
    submit = SubmitField('提交')

# 路由：主页
@app.route('/')
def index():
    return render_template('index.html')

# 路由：注册
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = RegistrationForm()
    if form.validate_on_submit():
        # 检查用户名是否已存在
        existing_user = User.query.filter_by(username=form.username.data).first()
        if existing_user:
            flash('该用户名已被注册')
            return redirect(url_for('register'))
        
        # 创建新用户
        hashed_password = generate_password_hash(form.password.data)
        new_user = User(
            username=form.username.data,
            password=hashed_password,
            phone=form.phone.data,
            address=form.address.data
        )
        db.session.add(new_user)
        db.session.commit()
        
        flash('注册成功！请登录')
        return redirect(url_for('login'))
    
    return render_template('register.html', form=form)

# 路由：登录
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and check_password_hash(user.password, form.password.data):
            login_user(user)
            flash('登录成功！')
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('index'))
        else:
            flash('登录失败，请检查用户名和密码')
    
    return render_template('login.html', form=form)

# 路由：登出
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('您已成功登出')
    return redirect(url_for('index'))

# 路由：菜品列表
@app.route('/dishes')
@app.route('/dishes/<int:restaurant_id>')
def dishes(restaurant_id=None):
    if restaurant_id:
        restaurant = Restaurant.query.get_or_404(restaurant_id)
        dishes = Dish.query.filter_by(restaurant_id=restaurant_id).all()
        return render_template('dishes.html', dishes=dishes, restaurant=restaurant)
    else:
        dishes = Dish.query.all()
        return render_template('dishes.html', dishes=dishes)

# 路由：添加菜品
@app.route('/dishes/add', methods=['GET', 'POST'])
@login_required
def add_dish():
    if not current_user.is_admin:
        flash('只有管理员可以添加菜品')
        return redirect(url_for('dishes'))
    
    form = DishForm()
    form.restaurant_id.choices = [(r.id, r.name) for r in Restaurant.query.all()]
    
    if form.validate_on_submit():
        dish = Dish(
            name=form.name.data,
            description=form.description.data,
            price=form.price.data,
            restaurant_id=form.restaurant_id.data
        )
        db.session.add(dish)
        db.session.commit()
        flash('菜品添加成功')
        return redirect(url_for('dishes', restaurant_id=dish.restaurant_id))
    return render_template('dish_form.html', form=form, title='添加菜品')

# 路由：编辑菜品
@app.route('/dishes/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_dish(id):
    if not current_user.is_admin:
        flash('只有管理员可以修改菜品')
        return redirect(url_for('dishes'))
    
    dish = Dish.query.get_or_404(id)
    form = DishForm(obj=dish)
    form.restaurant_id.choices = [(r.id, r.name) for r in Restaurant.query.all()]
    
    if form.validate_on_submit():
        dish.name = form.name.data
        dish.description = form.description.data
        dish.price = form.price.data
        dish.restaurant_id = form.restaurant_id.data
        db.session.commit()
        flash('菜品更新成功')
        return redirect(url_for('dishes', restaurant_id=dish.restaurant_id))
    return render_template('dish_form.html', form=form, title='编辑菜品')

# 路由：删除菜品
@app.route('/dishes/delete/<int:id>')
@login_required
def delete_dish(id):
    if not current_user.is_admin:
        flash('只有管理员可以删除菜品')
        return redirect(url_for('dishes'))
    
    dish = Dish.query.get_or_404(id)
    db.session.delete(dish)
    db.session.commit()
    flash('菜品删除成功')
    return redirect(url_for('dishes'))

# 路由：餐厅列表
@app.route('/restaurants')
def restaurants():
    restaurants = Restaurant.query.all()
    return render_template('restaurants.html', restaurants=restaurants)

# 路由：添加餐厅
@app.route('/restaurants/add', methods=['GET', 'POST'])
@login_required
def add_restaurant():
    if not current_user.is_admin:
        flash('只有管理员可以添加餐厅')
        return redirect(url_for('restaurants'))
    
    form = RestaurantForm()
    if form.validate_on_submit():
        restaurant = Restaurant(
            name=form.name.data,
            address=form.address.data,
            phone=form.phone.data,
            description=form.description.data
        )
        db.session.add(restaurant)
        db.session.commit()
        flash('餐厅添加成功')
        return redirect(url_for('restaurants'))
    return render_template('restaurant_form.html', form=form, title='添加餐厅')

# 路由：编辑餐厅
@app.route('/restaurants/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_restaurant(id):
    if not current_user.is_admin:
        flash('只有管理员可以修改餐厅信息')
        return redirect(url_for('restaurants'))
    
    restaurant = Restaurant.query.get_or_404(id)
    form = RestaurantForm(obj=restaurant)
    
    if form.validate_on_submit():
        restaurant.name = form.name.data
        restaurant.address = form.address.data
        restaurant.phone = form.phone.data
        restaurant.description = form.description.data
        db.session.commit()
        flash('餐厅信息更新成功')
        return redirect(url_for('restaurants'))
    return render_template('restaurant_form.html', form=form, title='编辑餐厅')

# 路由：删除餐厅
@app.route('/restaurants/delete/<int:id>')
@login_required
def delete_restaurant(id):
    if not current_user.is_admin:
        flash('只有管理员可以删除餐厅')
        return redirect(url_for('restaurants'))
    
    restaurant = Restaurant.query.get_or_404(id)
    db.session.delete(restaurant)
    db.session.commit()
    flash('餐厅删除成功')
    return redirect(url_for('restaurants'))

# 路由：收藏/取消收藏餐厅
@app.route('/restaurants/favorite/<int:id>')
@login_required
def toggle_favorite(id):
    restaurant = Restaurant.query.get_or_404(id)
    favorite = UserFavorite.query.filter_by(
        user_id=current_user.id,
        restaurant_id=id
    ).first()
    
    if favorite:
        db.session.delete(favorite)
        flash('已取消收藏')
    else:
        favorite = UserFavorite(user_id=current_user.id, restaurant_id=id)
        db.session.add(favorite)
        flash('已添加到收藏')
    
    db.session.commit()
    return redirect(url_for('restaurants'))

# 路由：我的收藏
@app.route('/favorites')
@login_required
def favorites():
    favorites = UserFavorite.query.filter_by(user_id=current_user.id).all()
    return render_template('restaurants.html', restaurants=[f.restaurant for f in favorites], show_favorites=True)

# 路由：订单列表
@app.route('/orders')
@login_required
@cache_order(timeout=60)  # 缓存订单列表1分钟
def orders():
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    if current_user.is_admin:
        # 使用分页查询替代全量加载
        orders = Order.query.order_by(Order.order_time.desc()).paginate(
            page=page, per_page=per_page, error_out=False)
    else:
        # 使用复合索引优化查询
        orders = Order.query.filter_by(user_id=current_user.id)\
            .order_by(Order.order_time.desc())\
            .paginate(page=page, per_page=per_page, error_out=False)
    
    return render_template('orders.html', orders=orders)

# 路由：创建订单
@app.route('/order', methods=['GET', 'POST'])
@login_required
@validate_data(OrderForm)
@check_data_integrity
def create_order():
    form = OrderForm()
    form.dish_id.choices = [(d.id, f"{d.name} (¥{d.price})") 
                           for d in Dish.query.filter_by(is_available=True).all()]
    
    if form.validate_on_submit():
        try:
            dish = Dish.query.get(form.dish_id.data)
            if not dish:
                flash('菜品不存在')
                return redirect(url_for('create_order'))
            
            # 创建订单对象
            order = Order(
                user_id=current_user.id,
                restaurant_id=dish.restaurant_id,
                total_amount=Decimal(str(dish.price * form.quantity.data)),
                delivery_address=current_user.address,
                note=form.note.data
            )
            
            order_detail = OrderDetail(
                order=order,
                dish_id=dish.id,
                quantity=form.quantity.data,
                unit_price=Decimal(str(dish.price)),
                subtotal=Decimal(str(dish.price * form.quantity.data))
            )
            
            # 数据验证
            if order_detail.quantity <= 0:
                raise ValueError("订单数量必须大于0")
            if order_detail.unit_price <= 0:
                raise ValueError("单价必须大于0")
            if order_detail.subtotal != order_detail.unit_price * order_detail.quantity:
                raise ValueError("订单金额计算错误")
            
            # 将订单添加到批处理队列
            with queue_lock:
                order_queue.append(order)
                order_queue.append(order_detail)
            
            # 如果队列达到批处理大小，触发处理
            if len(order_queue) >= BATCH_SIZE:
                process_order_batch()
            
            logging.info(f"用户 {current_user.id} 创建了新订单，订单ID: {order.id}")
            flash('订单创建成功')
            return redirect(url_for('orders'))
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"创建订单失败: {str(e)}")
            flash(f"创建订单失败: {str(e)}")
            return redirect(url_for('create_order'))
    
    return render_template('create_order.html', form=form)

# 路由：更新订单状态
@app.route('/orders/<int:id>/status/<status>')
@login_required
def update_order_status(id, status):
    if not current_user.is_admin:
        flash('只有管理员可以更新订单状态')
        return redirect(url_for('orders'))
    
    try:
        order = Order.query.get_or_404(id)
        new_status = OrderStatus(status)
        
        # 验证状态转换
        if not order.can_transition_to(new_status):
            flash(f'不能将订单从 {order.status.value} 转换为 {new_status.value}')
            return redirect(url_for('orders'))
        
        # 执行状态转换
        order.transition_to(new_status)
        db.session.commit()
        
        # 更新缓存
        cache_key = f"order_{id}"
        cache.delete(cache_key)
        
        logging.info(f"管理员 {current_user.id} 将订单 {id} 状态更新为 {status}")
        flash('订单状态已更新')
        
    except ValueError as e:
        logging.error(f"更新订单状态失败: {str(e)}")
        flash(str(e))
    except Exception as e:
        db.session.rollback()
        logging.error(f"更新订单状态时发生错误: {str(e)}")
        flash('更新订单状态失败')
    
    return redirect(url_for('orders'))

# 创建所有数据库表
def init_db():
    with app.app_context():
        db.drop_all()
        db.create_all()
        
        # 创建默认管理员用户
        admin = User(
            username='admin',
            password=generate_password_hash('admin123'),
            is_admin=True
        )
        db.session.add(admin)
        db.session.commit()

if __name__ == '__main__':
    init_db()  # 初始化数据库
    start_background_processing()  # 启动后台处理线程
    app.run(debug=True, port=5001)
import time
import psutil
import os
from app import app, db, Order, User, Restaurant, Dish, OrderDetail, OrderStatus
from memory_profiler import profile
import statistics
from concurrent.futures import ThreadPoolExecutor
import random
from decimal import Decimal
import logging
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PerformanceTest:
    def __init__(self):
        self.app = app
        self.ctx = self.app.app_context()
        self.ctx.push()
        
    def setup_test_data(self, num_orders=1000):
        """创建测试数据"""
        logger.info("开始创建测试数据...")
        
        # 创建测试用户
        user = User(username='test_user', password='test123')
        db.session.add(user)
        
        # 创建测试餐厅
        restaurant = Restaurant(name='Test Restaurant')
        db.session.add(restaurant)
        
        # 创建测试菜品
        dishes = []
        for i in range(10):
            dish = Dish(
                name=f'Test Dish {i}',
                price=Decimal(str(random.uniform(10.0, 100.0))),
                restaurant=restaurant,
                is_available=True
            )
            dishes.append(dish)
            db.session.add(dish)
        
        db.session.commit()
        
        # 创建测试订单
        start_time = time.time()
        orders_created = 0
        
        for i in range(num_orders):
            order = Order(
                user_id=user.id,
                restaurant_id=restaurant.id,
                total_amount=Decimal('0'),
                delivery_address='Test Address',
                status=random.choice(list(OrderStatus))
            )
            db.session.add(order)
            
            # 为每个订单添加1-5个订单明细
            total_amount = Decimal('0')
            for _ in range(random.randint(1, 5)):
                dish = random.choice(dishes)
                quantity = random.randint(1, 5)
                unit_price = dish.price
                subtotal = Decimal(str(unit_price * quantity))
                total_amount += subtotal
                
                detail = OrderDetail(
                    order=order,
                    dish_id=dish.id,
                    quantity=quantity,
                    unit_price=unit_price,
                    subtotal=subtotal
                )
                db.session.add(detail)
            
            order.total_amount = total_amount
            orders_created += 1
            
            # 每100个订单提交一次事务
            if orders_created % 100 == 0:
                db.session.commit()
                logger.info(f"已创建 {orders_created} 个订单...")
        
        db.session.commit()
        end_time = time.time()
        logger.info(f"测试数据创建完成！用时: {end_time - start_time:.2f} 秒")
        
        return user.id, restaurant.id, [d.id for d in dishes]

    def test_query_performance(self, user_id):
        """测试查询性能"""
        logger.info("开始测试查询性能...")
        
        # 测试带索引的查询
        start_time = time.time()
        orders = Order.query.filter_by(user_id=user_id, status=OrderStatus.PENDING).all()
        indexed_time = time.time() - start_time
        
        # 测试不带索引的复杂查询
        start_time = time.time()
        orders = Order.query.filter(
            db.and_(
                Order.user_id == user_id,
                Order.total_amount > 0,
                Order.order_time > datetime.now() - timedelta(days=30)
            )
        ).all()
        complex_time = time.time() - start_time
        
        return indexed_time, complex_time

    def test_batch_operations(self, user_id, restaurant_id, dish_ids):
        """测试批量操作性能"""
        logger.info("开始测试批量操作性能...")
        
        # 测试单条插入
        start_time = time.time()
        for _ in range(100):
            order = Order(
                user_id=user_id,
                restaurant_id=restaurant_id,
                total_amount=Decimal('10.00'),
                status=OrderStatus.PENDING
            )
            db.session.add(order)
            db.session.commit()
        single_insert_time = time.time() - start_time
        
        # 测试批量插入
        start_time = time.time()
        orders = []
        for _ in range(100):
            order = Order(
                user_id=user_id,
                restaurant_id=restaurant_id,
                total_amount=Decimal('10.00'),
                status=OrderStatus.PENDING
            )
            orders.append(order)
        db.session.bulk_save_objects(orders)
        db.session.commit()
        batch_insert_time = time.time() - start_time
        
        return single_insert_time, batch_insert_time

    def test_concurrent_operations(self, user_id, restaurant_id, dish_ids):
        """测试并发操作性能"""
        logger.info("开始测试并发操作性能...")
        
        def create_order():
            with app.app_context():
                order = Order(
                    user_id=user_id,
                    restaurant_id=restaurant_id,
                    total_amount=Decimal('10.00'),
                    status=OrderStatus.PENDING
                )
                db.session.add(order)
                db.session.commit()
                return order.id
        
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(create_order) for _ in range(100)]
            order_ids = [f.result() for f in futures]
        concurrent_time = time.time() - start_time
        
        return concurrent_time, len(order_ids)

    @profile
    def test_memory_usage(self):
        """测试内存使用"""
        logger.info("开始测试内存使用...")
        
        # 测试全量加载
        orders = Order.query.all()
        count1 = len(orders)
        
        # 测试分页加载
        page = Order.query.paginate(page=1, per_page=20)
        count2 = page.total
        
        return count1, count2

    def run_all_tests(self):
        """运行所有性能测试"""
        logger.info("开始全面性能测试...")
        
        try:
            # 初始化测试数据
            user_id, restaurant_id, dish_ids = self.setup_test_data()
            
            # 1. 测试查询性能
            indexed_time, complex_time = self.test_query_performance(user_id)
            query_improvement = ((complex_time - indexed_time) / complex_time) * 100
            
            # 2. 测试批量操作性能
            single_time, batch_time = self.test_batch_operations(user_id, restaurant_id, dish_ids)
            batch_improvement = ((single_time - batch_time) / single_time) * 100
            
            # 3. 测试并发性能
            concurrent_time, orders_created = self.test_concurrent_operations(user_id, restaurant_id, dish_ids)
            concurrent_rate = orders_created / concurrent_time
            
            # 4. 测试内存使用
            total_count, page_count = self.test_memory_usage()
            
            # 输出测试结果
            logger.info("\n性能测试结果:")
            logger.info(f"1. 查询性能:")
            logger.info(f"   - 索引查询时间: {indexed_time:.4f}秒")
            logger.info(f"   - 复杂查询时间: {complex_time:.4f}秒")
            logger.info(f"   - 性能提升: {query_improvement:.2f}%")
            
            logger.info(f"\n2. 批量操作性能:")
            logger.info(f"   - 单条插入时间: {single_time:.4f}秒")
            logger.info(f"   - 批量插入时间: {batch_time:.4f}秒")
            logger.info(f"   - 性能提升: {batch_improvement:.2f}%")
            
            logger.info(f"\n3. 并发性能:")
            logger.info(f"   - 总时间: {concurrent_time:.4f}秒")
            logger.info(f"   - 创建订单数: {orders_created}")
            logger.info(f"   - 每秒处理订单数: {concurrent_rate:.2f}")
            
            logger.info(f"\n4. 内存使用:")
            logger.info(f"   - 全量加载订单数: {total_count}")
            logger.info(f"   - 分页总订单数: {page_count}")
            
        except Exception as e:
            logger.error(f"性能测试过程中发生错误: {str(e)}")
            raise

if __name__ == '__main__':
    # 确保测试环境中的数据库是空的
    with app.app_context():
        db.drop_all()
        db.create_all()
    
    test = PerformanceTest()
    test.run_all_tests() 
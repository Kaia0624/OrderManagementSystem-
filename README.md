# OrderManagementSystem

## 1. 项目简介

本项目是一个**订餐管理系统**，旨在简化订餐流程、提高效率。该系统依托餐饮单位的组织结构，为用户提供在线订餐服务。餐饮单位可以是各种规模的餐厅、饭店或其他提供外卖服务的场所。

**主要功能**包括：

- **用户端**：在线浏览菜单、下单、管理个人信息、查看历史订单、收藏喜爱的餐厅。
- **餐厅端**：管理菜品、接收订单、处理订单、更新营业时间等。
- **系统管理员**：管理用户账户、管理餐厅信息、监控系统运行情况等。

总的来说，该系统旨在为用户提供便利的订餐体验，同时帮助餐饮单位提高订单处理效率和管理水平。

## 2. 功能描述

### 普通用户
- **管理需求**：
  - 注册账户、登录。
  - 编辑个人信息（用户名、电话、地址）。
  - 查看历史订单。
  - 收藏喜爱的餐厅。
  - 在线浏览菜单、下单。
- **信息需求**：
  - 个人账户信息。
  - 订单状态。
  - 菜单信息。

### 餐厅管理人员（管理员功能）
- **管理需求**：
  - 管理菜品（添加、编辑、删除、设置可用状态）。
  - 接收订单、处理订单、更新订单状态。
  - 查看订单历史。
  - 管理餐厅信息（添加、编辑、删除餐厅信息）。
- **信息需求**：
  - 订单信息。
  - 菜品信息。
  - 餐厅信息。

### 系统管理员（管理员功能）
- **管理需求**：
  - 管理用户账户。
  - 管理餐厅信息。
  - 监控系统运行情况。
- **信息需求**：
  - 用户信息。
  - 餐厅信息。
  - 订单信息。

## 3. 概念模型设计

本系统包含以下实体关系：

- **用户和订单**：一对多关系，一个用户可以拥有多个订单，一个订单只属于一个用户。
- **餐厅和菜品**：一对多关系，一个餐厅可以提供多个菜品，一个菜品只属于一个餐厅。
- **订单和订单明细**：一对多关系，一个订单可以包含多个订单明细，一个订单明细只属于一个订单。
- **用户和收藏表**：多对多关系，一个用户可以收藏多个餐厅，一个餐厅也可以被多个用户收藏。

## 4. 数据库逻辑模型设计

本系统包含以下数据表：

- **用户表 (Users)**：主码 `UserID`。
- **订单表 (Orders)**：主码 `OrderID`，外码 `UserID`（来自用户表）。
- **餐厅表 (Restaurants)**：主码 `RestaurantID`。
- **菜品表 (Dishs)**：主码 `DishID`，外码 `RestaurantID`（来自餐厅表）。
- **订单明细表 (OrderDetails)**：主码 `OrderDetailID`，外码 `OrderID`（来自订单表）、`DishID`（来自菜品表）。
- **收藏表 (UserFavorites)**：外码 `UserID`（来自用户表）、`RestaurantID`（来自餐厅表）。

## 5. 数据库物理模型

### Users (用户表)
- `UserID` (int, Not Null, Primary Key)：主键 ID。
- `UserName` (nvarchar(50), Not Null)：用户名。
- `Password` (nvarchar(50), Not Null)：密码。
- `PhoneNumber` (nvarchar(20))：手机号。
- `Address` (nvarchar(100))：地址。

### Restaurants (餐厅表)
- `RestaurantID` (int, Not Null, Primary Key)：主键 ID。
- `RestaurantName` (nvarchar(100), Not Null)：餐厅名称。
- `Address` (nvarchar(100), Not Null)：地址。
- `ContactInfo` (nvarchar(20), Not Null)：联系方式。
- `BusinessHours` (nvarchar(50), Not Null)：营业时间。

### Dishs (菜品表)
- `DishID` (int, Not Null, Primary Key)：主键 ID。
- `DishName` (nvarchar(100), Not Null)：菜品名称。
- `Description` (nvarchar(255))：描述。
- `Price` (decimal(10,2), Not Null)：价格。
- `RestaurantID` (int, Not Null, Foreign Key)：对应餐厅表的 `RestaurantID`。

### Orders (订单表)
- `OrderID` (int, Not Null, Primary Key)：主键 ID。
- `OrderTime` (datetime, Not Null)：订单时间。
- `OrderStatus` (nvarchar(20), Not Null)：订单状态。
- `TotalAmount` (decimal(10,2), Not Null)：订单总金额。
- `UserID` (int, Not Null, Foreign Key)：对应用户表的 `UserID`。
- `RestaurantID` (int, Not Null, Foreign Key)：对应餐厅表的 `RestaurantID`。

### OrderDetails (订单明细表)
- `OrderDetailID` (int, Not Null, Primary Key)：主键 ID。
- `Quantity` (int, Not Null)：数量。
- `UnitPrice` (decimal(10,2), Not Null)：单价。
- `Subtotal` (decimal(10,2), Not Null)：小计。
- `OrderID` (int, Not Null, Foreign Key)：对应订单表的 `OrderID`。
- `DishID` (int, Not Null, Foreign Key)：对应菜品表的 `DishID`。

### UserFavorites (用户收藏表)
- `UserID` (int, Not Null, Foreign Key)：对应用户表的 `UserID`。
- `RestaurantID` (int, Not Null, Foreign Key)：对应餐厅表的 `RestaurantID`。

## 6. 数据库操作示例

- **查询所有菜品名称和价格**：
  ```sql
  SELECT DishName, Price FROM Dishs;
  ```

- **查询所有订单状态为“完成”的订单**：
  ```sql
  SELECT * FROM Orders WHERE OrderStatus = '完成';
  ```

- **向 Dishs 表中增加一条新的菜品记录**：
  ```sql
  INSERT INTO Dishs (DishName, Description, Price, RestaurantID) 
  VALUES ('麻辣宫保鸡丁', '麻辣，微辣，不辣', 28.0, 1);
  ```

- **将 Dishs 表中 ID 为 3 的菜品价格修改为 35.0**：
  ```sql
  UPDATE Dishs SET Price = 35.0 WHERE DishID = 3;
  ```

## 7. 触发器

本项目创建了一个触发器，用于在菜品价格发生变化时，自动更新订单明细中的单价和小计。

- **触发器名称**：`trg_update_unit_price_and_subtotal`
- **触发条件**：当 `Dishs` 表的 `Price` 字段更新时。
- **触发操作**：更新 `OrderDetails` 表中对应菜品的 `UnitPrice` 和 `Subtotal`。

  ```sql
  CREATE OR ALTER TRIGGER trg_update_unit_price_and_subtotal
  ON Dishs
  AFTER UPDATE
  AS
  BEGIN
      UPDATE OrderDetails
      SET UnitPrice = i.Price,
          Subtotal = i.Price * Quantity
      FROM OrderDetails od
      INNER JOIN inserted i ON od.DishID = i.DishID
      INNER JOIN deleted d ON od.DishID = d.DishID
      WHERE od.DishID = i.DishID
      AND od.UnitPrice = d.Price;
  END;
  ```

## 8. 事务

本项目实现了事务处理，确保在更新菜品价格时，订单明细中的单价和小计同步更新，保证数据一致性。

  ```sql
  BEGIN TRANSACTION;
  BEGIN TRY
      UPDATE Dishs
      SET Price = 10
      WHERE DishID = 5;

      UPDATE OrderDetails
      SET UnitPrice = 10,
          Subtotal = 10 * Quantity
      WHERE DishID = 5;

      COMMIT TRANSACTION; -- 提交事务
  END TRY
  BEGIN CATCH
      ROLLBACK TRANSACTION; -- 回滚事务
  END CATCH;
  ```

## 9. 索引

为提升查询性能，对以下字段创建了索引：

- `Users` 表的 `UserName` 和 `Password`。
- `Restaurants` 表的 `RestaurantName`。
- `Dishs` 表的 `DishName`。
- `Orders` 表的 `OrderStatus`。

## 10. 视图

创建视图 `UserRestaurantOrderView`，用于查询用户姓名、餐厅名称、菜品名称和订单状态。

  ```sql
  CREATE VIEW UserRestaurantOrderView AS
  SELECT Users.UserName, Restaurants.RestaurantName, Dishs.DishName, Orders.OrderStatus
  FROM Orders
  JOIN Restaurants ON Orders.RestaurantID = Restaurants.RestaurantID
  JOIN Dishs ON Dishs.RestaurantID = Orders.RestaurantID
  JOIN Users ON Users.UserID = Orders.UserID;
  ```

## 11. 使用技术

- **后端框架**：Flask
- **ORM**：SQLAlchemy
- **数据库**：SQLite
- **前端框架**：Bootstrap 5.1.3
- **用户认证**：Flask-Login
- **表单处理**：WTForms

## 12. 如何运行

1. **安装依赖**：
   ```bash
   pip install -r requirements.txt
   ```

2. **初始化数据库**：
   - 确保已安装 SQLite。
   - 运行项目根目录下的 `app.py`，将自动创建 `ordersystem.db` 数据库文件。

3. **运行应用**：
   ```bash
   python app.py
   ```

4. **访问**：
   - 在浏览器中打开 `http://127.0.0.1:5001`。

5. **默认管理员账户**：
   - 用户名：`admin`
   - 密码：`admin123`

## 13. 项目总结

本项目实现了一个基本的订餐管理系统，涵盖用户管理、餐厅管理、菜品管理、订单管理和收藏功能。通过数据库设计、索引优化、触发器和事务等技术，保证了系统的数据一致性和查询性能。

## 14. 界面特点

- **响应式设计**：适配不同设备。
- **Bootstrap 5.1.3 UI 框架**：美观且易用。
- **清晰的导航栏**：方便操作。
- **模态框**：展示详细信息。
- **状态标签颜色区分**：直观显示订单状态。

## 15. 安全特性

- **密码加密存储**：保护用户隐私。
- **用户认证和授权**：确保访问安全。
- **CSRF 保护**：防止跨站请求伪造。
- **访问控制**：区分管理员和普通用户权限。
```

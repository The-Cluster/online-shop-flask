from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func

db = SQLAlchemy()

# ----------------------------------------------- Пользователь и товары -----------------------------------------------
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(32), unique=True)
    password = db.Column(db.String(32))

class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(12))
    name = db.Column(db.String(32), unique=True)
    url = db.Column(db.String(50))
    price = db.Column(db.Numeric(10, 2))

    sizes = db.relationship('Size', backref='product', lazy=True)

class Size(db.Model):
    __tablename__ = 'sizes'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'))
    name = db.Column(db.String(12))
    quantity = db.Column(db.Integer)



# ----------------------------------------------- Корзина и заказы --------------------------------------------------
class Cart(db.Model):
    __tablename__ = 'carts'
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), primary_key=True)
    size_id = db.Column(db.Integer, db.ForeignKey('sizes.id'), primary_key=True)
    quantity = db.Column(db.Integer)


class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    date = db.Column(db.DateTime)
    price = db.Column(db.Numeric(10, 2))
    info = db.Column(db.Text)
    status = db.Column(db.Text)

    order_products = db.relationship('OrderProduct', backref='order', lazy=True)

class OrderProduct(db.Model):
    __tablename__ = 'orders_products'
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), primary_key=True)
    size_id = db.Column(db.Integer, db.ForeignKey('sizes.id'), primary_key=True)
    quantity_ordered = db.Column(db.Integer)

    product = db.relationship('Product', backref='order_products')
import os
import json
from dotenv import load_dotenv
from models import db, User, Product, Size, Cart, Order, OrderProduct


from flask import Flask, Response, make_response, redirect, flash, url_for, render_template, g, request, session, abort, jsonify
from sqlalchemy import func

app = Flask(__name__)
load_dotenv()
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['SQLALCHEMY_DATABASE_URI']
app.secret_key = os.environ['SECRET_KEY']
db.init_app(app)

app.jinja_env.auto_reload = True

# Функция для получения количества товаров в корзине
def get_cart_count():
    if 'user_id' in session:
        return Cart.query.filter_by(user_id=session['user_id']).count()
    else:
        return 0

def get_username():
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        return user.username if user else None
    else:
        return None

@app.context_processor
def inject_cart_count():
    return dict(cart_count=get_cart_count())

@app.context_processor
def inject_username():
    return dict(username=get_username())




# -------------------------------------------------- Каталог --------------------------------------------------
@app.get('/')
def main():
    products = Product.query.all()
    return render_template('index.jinja', products=products)


@app.get('/catalog/shirts')
def catalog_shirts():
    products = Product.query.filter_by(type='tshirt').all()
    return render_template('index.jinja', products=products)

@app.get('/catalog/hats')
def catalog_hats():
    products = Product.query.filter_by(type='hat').all()
    return render_template('index.jinja', products=products)

@app.get('/catalog/shoes')
def catalog_shoes():
    products = Product.query.filter_by(type='shoes').all()
    return render_template('index.jinja', products=products)

# Страница товара
@app.route('/product/<product_name>')
def view_product(product_name):
    product_name = product_name.lower()
    product = Product.query.filter(func.lower(Product.name) == product_name.replace('_', ' ')).first()

    if product:
        sizes = Size.query.filter_by(product_id=product.id).all()

        # Проверяем, есть ли товар конкретного размера в корзине 
        in_cart = False
        if 'user_id' in session:
            user_cart = Cart.query.filter_by(user_id=session['user_id']).all()
            for cart_item in user_cart:
                if cart_item.product_id == product.id:
                    if cart_item.size_id in [size.id for size in sizes]:
                        in_cart = True
                        break

        return render_template('product.jinja', product=product, sizes=sizes, in_cart=in_cart)
    else:
        abort(404)
        
# ------------------------------------------------------------------------------------------------------------

@app.get('/orders')
def orders():
    if not 'user_id' in session:
        return redirect(url_for('login'))
    
    orders = db.session.query(Order).\
        filter(Order.user_id == session['user_id']).\
        order_by(Order.id.desc()).all()
    
    return render_template('orders.jinja', orders=orders)

# Обработка ошибок
@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.jinja'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('500.jinja'), 500

# -------------------------------------------------- Аутентификация --------------------------------------------------
# Страница личного кабинета
@app.get('/dashboard')
def dashboard():
    return render_template('dashboard.jinja')

# Страница авторизации
@app.get('/login')
def login():
    if 'user_username' in session:
        return redirect(url_for('main'))
    return render_template('auth.jinja', login=True)
# Вход в аккаунт
@app.post('/login')
def postLogin():
    username = request.form['username']
    password = request.form['password']
    
    user = User.query.filter_by(username=username, password=password).first()
    try:
        if user:
            # Аутентификация прошла успешно, устанавливаем id пользователя в сеансе
            session['user_id'] = user.id
            session['user_username'] = user.username
                    
            flash('Успешная авторизация')
            return redirect(url_for('main'))
        else:
            flash('Неправильный логин или пароль.')
            return redirect(url_for('login'))
    except Exception as e:
        flash(f"An error occurred: {str(e)}", 'error')

# Страница регистрации
@app.get('/signup')
def signup():
    if 'user_username' in session:
        return redirect(url_for('main'))
    return render_template('auth.jinja', signup=True)
# Регистрация
@app.post('/signup')
def postSignup():
    username = request.form['username']
    password = request.form['password']

    existing_user = User.query.filter_by(username=username).first()
    if existing_user:
        flash('Пользователь с данным логином уже существует. Пожалуйста, введите другой.')
        return redirect(url_for('signup'))
    else:
        new_user = User(username=username, password=password)
        db.session.add(new_user)
        db.session.commit()
        
        return redirect(url_for('login'))

# Выход из аккаунта
@app.get('/logout')
def logout():
    # Создаем объект ответа
    res = make_response(redirect(url_for('main')))

    # Удаляем куки по имени
    res.set_cookie('session', '', expires=0)

    # Очищаем данные сессии
    session.clear()

    return res

# ----------------------------------------------- Корзина и заказ -----------------------------------------------
# КОРЗИНА - страница
@app.get('/cart')
def cart():
    if not 'user_id' in session:
        return redirect(url_for('login'))

    # Получаем корзину пользователя из базы данных
    user_cart = db.session.query(Cart, Product, Size).\
        join(Product, Cart.product_id == Product.id).\
        join(Size, Cart.size_id == Size.id).\
        filter(Cart.user_id == session['user_id']).all()

    # user_cart будет список кортежей, каждый из которых будет содержать корзину, товар и размер
    

    # Проверяем наличие товаров в корзине, которых нет в наличии или количество превышает доступное
    unavailable = []
    for cart_item, product, size in user_cart:
        if size.quantity <= 0 or cart_item.quantity > size.quantity:
            unavailable.append(cart_item)
    
    total_price = sum(cart_item[1].price * cart_item[0].quantity for cart_item in user_cart)
    return render_template("cart.jinja", user_cart=user_cart, total_price=total_price, unavailable=unavailable)



# ТОВАР - добавить товар
@app.post('/add_to_cart')
def add_to_cart():
    if not 'user_id' in session:
        return redirect(url_for('login'))

    try:
        # Получаем данные из запроса
        product_id = request.form.get('product_id')
        size_id = request.form.get('size_id')
        quantity = request.form.get('quantity')
        user_id = session.get('user_id')
        
        check_quantity = Size.query.filter_by(id = size_id, product_id=product_id).first()
        print(check_quantity.quantity)
        if check_quantity.quantity <= 0:
            abort(500)
        # Создаем новый элемент корзины
        cart = Cart(user_id=user_id, product_id=product_id, size_id=size_id, quantity=quantity)


        # Добавляем элемент в базу данных
        db.session.add(cart)
        db.session.commit()

        jsonify({'message': 'Товар успешно добавлен в корзину'})
        return redirect(url_for('cart'))
    
    except:
        # Если возникает ошибка IntegrityError (дубликат ключа), перенаправляем пользователя на страницу корзины
        return redirect(url_for('cart'))



# КОРЗИНА - удалить товар
@app.post('/remove_from_cart')
def remove_from_cart():
    if not 'user_id' in session:
        return redirect(url_for('login'))
    
    user_id = session.get('user_id')
    product_id = request.form.get('product_id')
    size_id = request.form.get('size_id')

    # Находим предмет в корзине
    cart_item = Cart.query.filter_by(user_id=user_id, product_id=product_id, size_id=size_id).first()

    if cart_item:
        # Удаляем предмет из корзины
        db.session.delete(cart_item)
        db.session.commit()
        flash('Предмет успешно удален из корзины.')
    else:
        flash('Не удалось найти предмет в корзине.')

    # Перенаправляем пользователя на страницу корзины
    return redirect(url_for('cart'))



@app.post('/place_an_order')
def place_an_order():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        # Проверяем наличие данных в форме
        if not all(key in request.form for key in ['first_name', 'last_name', 'address', 'city', 'zip_code']):
            raise ValueError("Не все данные для оформления заказа были предоставлены.")

        first_name = request.form['first_name']
        last_name = request.form['last_name']
        address = request.form['address']
        city = request.form['city']
        zip_code = request.form['zip_code']

        # Создаем информацию о заказе
        info = f"{first_name} {last_name}, {city} {address}, {zip_code}"
        print(info)

        # Получаем корзину пользователя из базы данных
        user_cart = db.session.query(Cart, Product, Size).\
            join(Product, Cart.product_id == Product.id).\
            join(Size, Cart.size_id == Size.id).\
            filter(Cart.user_id == session['user_id']).all()

        # Добавляем заказ
        order = Order(user_id=session['user_id'], date=db.func.current_timestamp(), price=sum(cart_item[1].price * cart_item[0].quantity for cart_item in user_cart), info=info, status="В пути")
        db.session.add(order)
        db.session.commit()  # Коммитим заказ, чтобы получить его id

        decline = False

        # Добавляем товары
        for cart_item, product, size in user_cart:
            order_product = OrderProduct(order_id=order.id, product_id=product.id, size_id=size.id, quantity_ordered=cart_item.quantity)

            # Уменьшаем количество определенного размера товара
            if size.quantity - cart_item.quantity < 0:
                decline = True
                db.session.delete(cart_item)
                db.session.commit()
                break
    
            size.quantity -= cart_item.quantity
            db.session.add(size) 
            # Удаляем с корзины
            db.session.delete(cart_item)
            #Добавляем товары в заказ
            db.session.add(order_product)
            db.session.commit()

        if decline:
            db.session.delete(order)
            db.session.commit()
            return "Количество товара в корзине превышает доступное количество!", 400

        # Выполняем все изменения в базе данных
        db.session.commit()
        return redirect(url_for('orders'))
    except Exception as e:
        # Логируем ошибку
        print(f"Ошибка при оформлении заказа: {str(e)}")
        return redirect(url_for('cart'))




# Фильтр для преобразования названия месяца на русский язык
def russian_month(date):
    month_names = {
        'January': 'Январь',
        'February': 'Февраль',
        'March': 'Март',
        'April': 'Апрель',
        'May': 'Май',
        'June': 'Июнь',
        'July': 'Июль',
        'August': 'Август',
        'September': 'Сентябрь',
        'October': 'Октябрь',
        'November': 'Ноябрь',
        'December': 'Декабрь'
    }
    return month_names[date.strftime('%B')]
# Регистрация фильтра в шаблоне
app.jinja_env.filters['russian_month'] = russian_month


if __name__ == '__main__':
    app.run(debug=True)


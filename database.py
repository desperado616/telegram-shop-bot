import sqlite3
import logging
from datetime import datetime
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, db_name: str = 'shop_bot.db'):
        self.db_name = db_name
        self.init_db()

    def get_connection(self):
        conn = sqlite3.connect(self.db_name)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        """Инициализация всех таблиц"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Пользователи
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                phone TEXT,
                is_premium BOOLEAN DEFAULT FALSE,
                orders_count INTEGER DEFAULT 0,
                total_spent REAL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Товары
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                price REAL NOT NULL,
                category TEXT NOT NULL,
                image_url TEXT,
                is_available BOOLEAN DEFAULT TRUE,
                is_popular BOOLEAN DEFAULT FALSE
            )
        ''')

        # Корзина
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cart (
                user_id INTEGER,
                product_id INTEGER,
                quantity INTEGER DEFAULT 1,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, product_id),
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (product_id) REFERENCES products (id)
            )
        ''')

        # Заказы
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                total_amount REAL,
                delivery_address TEXT,
                delivery_time TEXT,
                status TEXT DEFAULT 'new',
                payment_method TEXT,
                phone_number TEXT,
                comments TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')

        # Элементы заказа
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS order_items (
                order_id INTEGER,
                product_id INTEGER,
                quantity INTEGER,
                price REAL,
                FOREIGN KEY (order_id) REFERENCES orders (id),
                FOREIGN KEY (product_id) REFERENCES products (id)
            )
        ''')

        # Отзывы
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                rating INTEGER CHECK(rating >= 1 AND rating <= 5),
                comment TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')

        # Промокоды
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS promo_codes (
                code TEXT PRIMARY KEY,
                discount_percent INTEGER DEFAULT 0,
                discount_amount REAL DEFAULT 0,
                min_order_amount REAL DEFAULT 0,
                usage_limit INTEGER DEFAULT 1,
                used_count INTEGER DEFAULT 0,
                expires_at TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE
            )
        ''')

        # Добавляем тестовые данные
        self._add_sample_data(cursor)

        conn.commit()
        conn.close()

    def _add_sample_data(self, cursor):
        """Добавляем тестовые товары"""
        products = [
            # Пиццы
            ("Пепперони", "Пицца с пепперони и сыром моцарелла", 450, "pizza", None, True),
            ("Маргарита", "Классическая пицца с томатами и моцареллой", 400, "pizza", None, True),
            ("4 Сыра", "Пицца с моцареллой, горгонзолой, пармезаном и рикоттой", 500, "pizza", None, True),
            ("Гавайская", "Пицца с ветчиной и ананасами", 480, "pizza", None, False),
            ("Мясная", "Пицца с колбасками, беконом и ветчиной", 520, "pizza", None, True),

            # Бургеры
            ("Чизбургер", "Бургер с говяжьей котлетой и сыром", 280, "burger", None, True),
            ("Чикенбургер", "Бургер с куриной котлетой", 250, "burger", None, True),
            ("Двойной бургер", "Двойная говяжья котлета с беконом", 450, "burger", None, True),
            ("Вегетарианский", "Бургер с овощной котлетой", 300, "burger", None, False),

            # Суши
            ("Филадельфия", "Лосось, сливочный сыр, огурец", 580, "sushi", None, True),
            ("Калифорния", "Краб, авокадо, огурец, икра", 520, "sushi", None, True),
            ("Запеченные роллы", "Роллы с лососем под соусом", 480, "sushi", None, True),

            # Напитки
            ("Кола", "Coca-Cola 0.5л", 120, "drink", None, True),
            ("Фанта", "Fanta 0.5л", 120, "drink", None, True),
            ("Кофе", "Американо", 150, "drink", None, True),
            ("Чай", "Черный или зеленый чай", 100, "drink", None, True),
            ("Сок", "Апельсиновый сок 0.3л", 130, "drink", None, False),

            # Десерты
            ("Тирамису", "Классический итальянский десерт", 300, "dessert", None, True),
            ("Чизкейк", "Нью-йоркский чизкейк", 350, "dessert", None, True),
            ("Мороженое", "Пломбир ванильный", 200, "dessert", None, True),

            # Салаты
            ("Цезарь", "Салат Цезарь с курицей", 320, "salad", None, True),
            ("Греческий", "Овощной салат с сыром фета", 280, "salad", None, True),
        ]

        # Проверяем, есть ли уже товары
        cursor.execute("SELECT COUNT(*) FROM products")
        if cursor.fetchone()[0] == 0:
            cursor.executemany(
                "INSERT INTO products (name, description, price, category, image_url, is_popular) VALUES (?, ?, ?, ?, ?, ?)",
                products
            )

        # Добавляем тестовые промокоды
        promo_codes = [
            ("WELCOME10", 10, 0, 500, 100, 0, None),
            ("FIRSTORDER", 15, 0, 1000, 1, 0, None),
            ("PREMIUM20", 20, 0, 0, 1000, 0, None),
        ]

        cursor.execute("SELECT COUNT(*) FROM promo_codes")
        if cursor.fetchone()[0] == 0:
            cursor.executemany(
                "INSERT INTO promo_codes (code, discount_percent, discount_amount, min_order_amount, usage_limit, used_count, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                promo_codes
            )

    # Методы для работы с пользователями
    def get_or_create_user(self, user_id: int, username: str = "", first_name: str = ""):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "INSERT OR IGNORE INTO users (id, username, first_name) VALUES (?, ?, ?)",
            (user_id, username, first_name)
        )

        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        user = dict(cursor.fetchone())
        conn.close()
        return user

    def update_user_phone(self, user_id: int, phone: str):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET phone = ? WHERE id = ?", (phone, user_id))
        conn.commit()
        conn.close()

    def set_premium(self, user_id: int, is_premium: bool):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET is_premium = ? WHERE id = ?", (is_premium, user_id))
        conn.commit()
        conn.close()

    # Методы для работы с товарами
    def get_categories(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT category FROM products WHERE is_available = TRUE")
        categories = [row['category'] for row in cursor.fetchall()]
        conn.close()
        return categories

    def get_products_by_category(self, category: str):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM products WHERE category = ? AND is_available = TRUE ORDER BY is_popular DESC, name",
            (category,)
        )
        products = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return products

    def get_popular_products(self, limit: int = 6):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM products WHERE is_popular = TRUE AND is_available = TRUE LIMIT ?",
            (limit,)
        )
        products = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return products

    def get_product(self, product_id: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    # Методы для работы с корзиной
    def get_cart(self, user_id: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT c.*, p.name, p.price, p.description 
            FROM cart c 
            JOIN products p ON c.product_id = p.id 
            WHERE c.user_id = ?
        ''', (user_id,))
        cart_items = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return cart_items

    def add_to_cart(self, user_id: int, product_id: int, quantity: int = 1):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO cart (user_id, product_id, quantity) 
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, product_id) 
            DO UPDATE SET quantity = quantity + excluded.quantity
        ''', (user_id, product_id, quantity))
        conn.commit()
        conn.close()

    def update_cart_item(self, user_id: int, product_id: int, quantity: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        if quantity <= 0:
            cursor.execute("DELETE FROM cart WHERE user_id = ? AND product_id = ?", (user_id, product_id))
        else:
            cursor.execute(
                "UPDATE cart SET quantity = ? WHERE user_id = ? AND product_id = ?",
                (quantity, user_id, product_id)
            )
        conn.commit()
        conn.close()

    def clear_cart(self, user_id: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM cart WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()

    # Методы для работы с заказами
    def create_order(self, order_data: Dict[str, Any]) -> int:
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO orders (user_id, total_amount, delivery_address, delivery_time, payment_method, phone_number, comments)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            order_data['user_id'],
            order_data['total_amount'],
            order_data['delivery_address'],
            order_data['delivery_time'],
            order_data['payment_method'],
            order_data.get('phone_number'),
            order_data.get('comments')
        ))

        order_id = cursor.lastrowid

        # Добавляем товары заказа
        for item in order_data['items']:
            cursor.execute('''
                INSERT INTO order_items (order_id, product_id, quantity, price)
                VALUES (?, ?, ?, ?)
            ''', (order_id, item['product_id'], item['quantity'], item['price']))

        # Обновляем статистику пользователя
        cursor.execute('''
            UPDATE users 
            SET orders_count = orders_count + 1, total_spent = total_spent + ? 
            WHERE id = ?
        ''', (order_data['total_amount'], order_data['user_id']))

        # Очищаем корзину
        cursor.execute("DELETE FROM cart WHERE user_id = ?", (order_data['user_id'],))

        conn.commit()
        conn.close()
        return order_id

    def get_user_orders(self, user_id: int, limit: int = 10):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM orders 
            WHERE user_id = ? 
            ORDER BY created_at DESC 
            LIMIT ?
        ''', (user_id, limit))
        orders = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return orders

    def get_order_details(self, order_id: int):
        conn = self.get_connection()
        cursor = conn.cursor()

        # Получаем заказ
        cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        order = dict(cursor.fetchone())

        # Получаем товары заказа
        cursor.execute('''
            SELECT oi.*, p.name 
            FROM order_items oi 
            JOIN products p ON oi.product_id = p.id 
            WHERE oi.order_id = ?
        ''', (order_id,))
        order['items'] = [dict(row) for row in cursor.fetchall()]

        conn.close()
        return order

    # Методы для работы с отзывами
    def add_review(self, user_id: int, rating: int, comment: str):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO reviews (user_id, rating, comment) 
            VALUES (?, ?, ?)
        ''', (user_id, rating, comment))
        conn.commit()
        conn.close()

    def get_reviews(self, limit: int = 10):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT r.*, u.first_name, u.username 
            FROM reviews r 
            JOIN users u ON r.user_id = u.id 
            ORDER BY r.created_at DESC 
            LIMIT ?
        ''', (limit,))
        reviews = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return reviews

    def get_average_rating(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT AVG(rating) as avg_rating FROM reviews")
        result = cursor.fetchone()
        conn.close()
        return result['avg_rating'] if result['avg_rating'] else 0

    # Методы для работы с промокодами
    def get_promo_code(self, code: str):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM promo_codes WHERE code = ? AND is_active = TRUE", (code,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def use_promo_code(self, code: str):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE promo_codes 
            SET used_count = used_count + 1 
            WHERE code = ? AND (usage_limit = 0 OR used_count < usage_limit)
        ''', (code,))
        conn.commit()
        conn.close()

        def get_user_stats(self, user_id: int):
            """Получает статистику пользователя"""
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT 
                    orders_count,
                    total_spent,
                    is_premium,
                    created_at
                FROM users 
                WHERE id = ?
            ''', (user_id,))

            result = cursor.fetchone()
            conn.close()

            return dict(result) if result else None

        def get_favorite_categories(self, user_id: int):
            """Получает любимые категории пользователя"""
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT p.category, COUNT(*) as order_count
                FROM order_items oi
                JOIN orders o ON oi.order_id = o.id
                JOIN products p ON oi.product_id = p.id
                WHERE o.user_id = ?
                GROUP BY p.category
                ORDER BY order_count DESC
                LIMIT 3
            ''', (user_id,))

            categories = [dict(row) for row in cursor.fetchall()]
            conn.close()

            return categories
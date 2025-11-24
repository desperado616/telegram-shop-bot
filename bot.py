import logging
import asyncio
from telegram import Update, InputFile
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler
)
from datetime import datetime, timedelta
import json
import random
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from database import Database
import keyboards
import config

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
ADDRESS, DELIVERY_TIME, PHONE, COMMENTS, PAYMENT, PROMO_CODE, REVIEW_COMMENT = range(7)

# Инициализация базы данных
db = Database()


class ShopBot:
    def __init__(self):
        self.db = db
        self.user_sessions = {}  # Временные данные пользователей

    def get_session(self, user_id: int):
        """Получает или создает сессию пользователя"""
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = {
                'current_order': {},
                'promo_code': None,
                'promo_discount': 0
            }
        return self.user_sessions[user_id]

    def clear_session(self, user_id: int):
        """Очищает сессию пользователя"""
        if user_id in self.user_sessions:
            del self.user_sessions[user_id]

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /start"""
        user = update.effective_user
        user_id = user.id

        # Регистрируем пользователя
        user_data = self.db.get_or_create_user(user_id, user.username, user.first_name)

        welcome_text = f"""
🤖 **Добро пожаловать, {user.first_name}!**

🍕 **Доставка еды №1 в вашем городе!**

✨ **Что я умею:**
• 📋 Показать меню с 50+ позициями
• 🛒 Собирать корзину и оформлять заказы
• 🚚 Быстрая доставка за 30-60 минут
• 💎 Премиум-подписка со скидками
• ⭐ Система отзывов и рейтингов
• 🎁 Промокоды и акции

🎯 **Новинки этой недели:**
• 🍣 Новые роллы "Филадельфия премиум"
• 🍔 Бургер "Монстр" с тройной котлетой
• 🍰 Сезонные десерты

Выберите раздел ниже 👇
        """

        await update.message.reply_text(
            welcome_text,
            reply_markup=keyboards.main_menu(),
            parse_mode='Markdown'
        )

    async def show_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает меню с категориями"""
        categories = self.db.get_categories()

        categories_text = "📋 **Выберите категорию:**\n\n"
        for category in categories:
            emoji = config.CATEGORIES.get(category, '📦')
            categories_text += f"{emoji} {config.CATEGORIES.get(category, category)}\n"

        await update.message.reply_text(
            categories_text,
            reply_markup=keyboards.categories_keyboard(categories),
            parse_mode='Markdown'
        )

    async def show_loyalty(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает программу лояльности"""
        user_id = update.effective_user.id
        user_data = self.db.get_or_create_user(user_id)

        # Рассчитываем скидку на основе потраченной суммы
        total_spent = user_data.get('total_spent', 0)
        orders_count = user_data.get('orders_count', 0)

        # Уровни лояльности
        if total_spent >= 10000:
            level = "👑 Золотой"
            discount = 15
            next_level = "Максимальный уровень!"
        elif total_spent >= 5000:
            level = "🥈 Серебряный"
            discount = 10
            next_level = f"До золотого уровня: {10000 - total_spent}₽"
        elif total_spent >= 1000:
            level = "🥉 Бронзовый"
            discount = 5
            next_level = f"До серебряного уровня: {5000 - total_spent}₽"
        else:
            level = "🌟 Начальный"
            discount = 0
            next_level = f"До бронзового уровня: {1000 - total_spent}₽"

        text = f"""
    🎁 **Программа лояльности**

    📊 **Ваш статус:** {level}
    💵 **Всего потрачено:** {total_spent}₽
    📦 **Количество заказов:** {orders_count}
    💰 **Текущая скидка:** {discount}%

    🚀 **Следующий уровень:**
    {next_level}

    ✨ **Преимущества программы:**
    • 🎁 Персональные скидки
    • 🚀 Приоритетная доставка
    • 💫 Эксклюзивные предложения
    • 🎯 Персональные рекомендации

    💎 *Закажите еще на {max(0, 1000 - total_spent)}₽ для получения скидки!*
        """

        keyboard = [
            [InlineKeyboardButton("📋 Сделать заказ", callback_data="back_categories")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back_main")]
        ]

        if hasattr(update, 'message'):
            await update.message.reply_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        else:
            query = update.callback_query
            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )

            async def quick_reorder(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
                """Быстрый повтор последнего заказа"""
                user_id = update.effective_user.id
                orders = self.db.get_user_orders(user_id, limit=1)

                if not orders:
                    if hasattr(update, 'message'):
                        await update.message.reply_text(
                            "❌ У вас нет предыдущих заказов для повтора.",
                            parse_mode='Markdown'
                        )
                    else:
                        query = update.callback_query
                        await query.edit_message_text(
                            "❌ У вас нет предыдущих заказов для повтора.",
                            parse_mode='Markdown'
                        )
                    return

                last_order = self.db.get_order_details(orders[0]['id'])

                # Добавляем товары из последнего заказа в корзину
                for item in last_order['items']:
                    self.db.add_to_cart(user_id, item['product_id'], item['quantity'])

                text = f"""
            🔄 **Последний заказ #{last_order['id']} добавлен в корзину!**

            📦 **Добавлено товаров:** {len(last_order['items'])}
            💰 **Сумма заказа:** {last_order['total_amount']}₽

            Перейдите в корзину для оформления заказа.
                """

                keyboard = [
                    [InlineKeyboardButton("🛒 Перейти в корзину", callback_data="back_cart")],
                    [InlineKeyboardButton("📋 Смотреть меню", callback_data="back_categories")],
                    [InlineKeyboardButton("🔙 Назад", callback_data="back_main")]
                ]

                if hasattr(update, 'message'):
                    await update.message.reply_text(
                        text,
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        parse_mode='Markdown'
                    )
                else:
                    query = update.callback_query
                    await query.edit_message_text(
                        text,
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        parse_mode='Markdown'
                    )

    async def show_recommendations(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает рекомендованные товары на основе истории"""
        user_id = update.effective_user.id
        user_data = self.db.get_or_create_user(user_id)

        # Простая логика рекомендаций
        orders = self.db.get_user_orders(user_id, limit=5)

        if orders:
            # Рекомендуем популярные товары из категорий, которые пользователь уже заказывал
            text = "🎯 **Рекомендуем вам:**\n\n"
            popular_products = self.db.get_popular_products(limit=4)
        else:
            # Для новых пользователей показываем самые популярные товары
            text = "🔥 **Популярные товары:**\n\n"
            popular_products = self.db.get_popular_products(limit=6)

        if not popular_products:
            text += "😔 Пока нет рекомендаций. Сделайте первый заказ!"
        else:
            for product in popular_products:
                text += f"• {product['name']} - {product['price']}₽\n"
                text += f"  _{product['description']}_\n\n"

        keyboard = [
            [InlineKeyboardButton("🛒 Добавить в корзину", callback_data="back_categories")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back_main")]
        ]

        if hasattr(update, 'message'):
            await update.message.reply_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        else:
            query = update.callback_query
            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
    async def show_popular(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает популярные товары"""
        query = update.callback_query
        await query.answer()

        popular_products = self.db.get_popular_products()

        if not popular_products:
            await query.edit_message_text("😔 Популярные товары временно отсутствуют")
            return

        text = "🔥 **Популярные товары:**\n\n"
        for product in popular_products:
            text += f"• {product['name']} - {product['price']}₽\n"
            text += f"  _{product['description']}_\n\n"

        await query.edit_message_text(
            text,
            reply_markup=keyboards.products_keyboard(popular_products, "main"),
            parse_mode='Markdown'
        )

    async def show_category(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает товары в категории"""
        query = update.callback_query
        await query.answer()

        category = query.data.replace('cat_', '')
        products = self.db.get_products_by_category(category)

        if not products:
            await query.edit_message_text("😔 В этой категории пока нет товаров")
            return

        category_name = config.CATEGORIES.get(category, category)
        text = f"{category_name}\n\n**Выберите товар:**\n\n"

        for product in products:
            popular = " 🔥" if product['is_popular'] else ""
            text += f"• {product['name']} - {product['price']}₽{popular}\n"

        await query.edit_message_text(
            text,
            reply_markup=keyboards.products_keyboard(products),
            parse_mode='Markdown'
        )

    async def show_product(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает детали товара"""
        query = update.callback_query
        await query.answer()

        product_id = int(query.data.replace('prod_', ''))
        product = self.db.get_product(product_id)

        if not product:
            await query.edit_message_text("❌ Товар не найден")
            return

        # Проверяем есть ли товар в корзине
        user_id = query.from_user.id
        cart = self.db.get_cart(user_id)
        in_cart = any(item['product_id'] == product_id for item in cart)

        text = f"""
**{product['name']}**

{product['description']}

💵 **Цена:** {product['price']}₽
📦 **Категория:** {config.CATEGORIES.get(product['category'], product['category'])}
{"🔥 **Популярный товар!**" if product['is_popular'] else ""}
        """

        await query.edit_message_text(
            text,
            reply_markup=keyboards.product_keyboard(product_id, in_cart),
            parse_mode='Markdown'
        )

    async def add_to_cart(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Добавляет товар в корзину"""
        query = update.callback_query
        await query.answer()

        user_id = query.from_user.id
        product_id = int(query.data.replace('add_', ''))

        self.db.add_to_cart(user_id, product_id)

        await query.edit_message_text(
            "✅ **Товар добавлен в корзину!**\n\nПерейдите в корзину для оформления заказа.",
            parse_mode='Markdown'
        )

    async def update_cart_quantity(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Изменяет количество товара в корзине"""
        query = update.callback_query
        await query.answer()

        user_id = query.from_user.id
        data = query.data

        if data.startswith('inc_'):
            product_id = int(data.replace('inc_', ''))
            self.db.add_to_cart(user_id, product_id)
            await self.show_product(update, context)

        elif data.startswith('dec_'):
            product_id = int(data.replace('dec_', ''))
            cart = self.db.get_cart(user_id)
            for item in cart:
                if item['product_id'] == product_id:
                    new_quantity = max(0, item['quantity'] - 1)
                    self.db.update_cart_item(user_id, product_id, new_quantity)
                    break
            await self.show_product(update, context)

        elif data.startswith('cart_inc_'):
            product_id = int(data.replace('cart_inc_', ''))
            self.db.add_to_cart(user_id, product_id)
            await self.show_cart(update, context)

        elif data.startswith('cart_dec_'):
            product_id = int(data.replace('cart_dec_', ''))
            cart = self.db.get_cart(user_id)
            for item in cart:
                if item['product_id'] == product_id:
                    new_quantity = max(0, item['quantity'] - 1)
                    self.db.update_cart_item(user_id, product_id, new_quantity)
                    break
            await self.show_cart(update, context)

        elif data.startswith('cart_del_'):
            product_id = int(data.replace('cart_del_', ''))
            self.db.update_cart_item(user_id, product_id, 0)
            await self.show_cart(update, context)

    async def show_cart(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает корзину"""
        user_id = update.effective_user.id
        cart_items = self.db.get_cart(user_id)

        if not cart_items:
            text = "🛒 **Ваша корзина пуста**\n\nДобавьте товары из меню!"
            keyboard = keyboards.InlineKeyboardMarkup([
                [keyboards.InlineKeyboardButton("📋 Перейти в меню", callback_data="back_categories")],
                [keyboards.InlineKeyboardButton("🔙 Назад", callback_data="back_main")]
            ])
        else:
            text = "🛒 **Ваша корзина:**\n\n"
            total = 0

            for item in cart_items:
                item_total = item['price'] * item['quantity']
                total += item_total
                text += f"• {item['name']} x{item['quantity']} - {item_total}₽\n"

            # Применяем промокод если есть
            session = self.get_session(user_id)
            promo_discount = session.get('promo_discount', 0)

            if promo_discount > 0:
                discount_amount = total * (promo_discount / 100)
                total_after_discount = total - discount_amount
                text += f"\n🎁 **Скидка по промокоду:** -{discount_amount:.0f}₽"
                total = total_after_discount

            # Проверяем премиум для скидки
            user_data = self.db.get_or_create_user(user_id)
            if user_data['is_premium']:
                premium_discount = total * 0.1  # 10% скидка
                total_after_premium = total - premium_discount
                text += f"\n💎 **Премиум скидка:** -{premium_discount:.0f}₽"
                total = total_after_premium

            # Добавляем доставку
            delivery_cost = 0 if total >= config.FREE_DELIVERY_THRESHOLD else config.DELIVERY_PRICE
            if delivery_cost > 0:
                text += f"\n🚚 **Доставка:** {delivery_cost}₽"
            else:
                text += f"\n🚚 **Доставка:** бесплатно"

            total += delivery_cost
            text += f"\n💵 **Итого к оплате:** {total:.0f}₽"

            # Сохраняем итоговую сумму в сессии
            session['current_order']['total_amount'] = total
            session['current_order']['delivery_cost'] = delivery_cost

            keyboard = keyboards.cart_keyboard(cart_items)

        if hasattr(update, 'message'):
            await update.message.reply_text(text, reply_markup=keyboard, parse_mode='Markdown')
        else:
            await update.callback_query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')

    async def clear_cart(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Очищает корзину"""
        query = update.callback_query
        await query.answer()

        user_id = query.from_user.id
        self.db.clear_cart(user_id)
        self.clear_session(user_id)  # Очищаем сессию тоже

        await query.edit_message_text(
            "🗑 **Корзина очищена!**",
            parse_mode='Markdown'
        )

    async def start_checkout(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начинает оформление заказа"""
        query = update.callback_query
        await query.answer()

        user_id = query.from_user.id
        cart_items = self.db.get_cart(user_id)

        if not cart_items:
            await query.edit_message_text("❌ Корзина пуста!")
            return

        await query.edit_message_text(
            "🚚 **Оформление заказа**\n\n📮 Пожалуйста, введите адрес доставки:",
            parse_mode='Markdown'
        )

        return ADDRESS

    async def process_address(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает ввод адреса"""
        user_id = update.effective_user.id
        address = update.message.text

        session = self.get_session(user_id)
        session['current_order']['delivery_address'] = address

        await update.message.reply_text(
            "⏱ **Выберите время доставки:**",
            reply_markup=keyboards.delivery_time_keyboard(),
            parse_mode='Markdown'
        )

        return DELIVERY_TIME

    async def process_delivery_time(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает выбор времени доставки"""
        query = update.callback_query
        await query.answer()

        user_id = query.from_user.id
        data = query.data

        time_mapping = {
            'time_asap': 'Как можно скорее',
            'time_1h': 'В течение часа',
            'time_2h': 'Через 2 часа',
            'time_custom': 'Указать своё время'
        }

        if data == 'time_custom':
            await query.edit_message_text("⏱ Введите желаемое время доставки (например: 'сегодня в 19:30'):")
            return DELIVERY_TIME

        session = self.get_session(user_id)
        session['current_order']['delivery_time'] = time_mapping.get(data, data)

        # Проверяем есть ли телефон у пользователя
        user_data = self.db.get_or_create_user(user_id)

        if user_data.get('phone'):
            session['current_order']['phone_number'] = user_data['phone']
            await query.edit_message_text(
                "📝 **Хотите добавить комментарий к заказу?**\n\nНапример: 'Позвонить за 15 минут', 'Оставить у двери' и т.д.",
                reply_markup=keyboards.yes_no_keyboard(),
                parse_mode='Markdown'
            )
            return COMMENTS
        else:
            await query.edit_message_text(
                "📞 **Введите ваш номер телефона для связи:**\n\nФормат: +7XXXYYYYYYY",
                parse_mode='Markdown'
            )
            return PHONE

    async def process_phone(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает ввод телефона"""
        user_id = update.effective_user.id
        phone = update.message.text

        # Простая валидация номера
        if not any(char.isdigit() for char in phone) or len(phone) < 10:
            await update.message.reply_text("❌ Пожалуйста, введите корректный номер телефона:")
            return PHONE

        session = self.get_session(user_id)
        session['current_order']['phone_number'] = phone

        # Сохраняем телефон в базу
        self.db.update_user_phone(user_id, phone)

        await update.message.reply_text(
            "📝 **Хотите добавить комментарий к заказу?**",
            reply_markup=keyboards.yes_no_keyboard(),
            parse_mode='Markdown'
        )

        return COMMENTS

    async def process_comments(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает комментарии к заказу"""
        query = update.callback_query
        await query.answer()

        user_id = query.from_user.id
        data = query.data

        if data == 'yes':
            await query.edit_message_text("💬 Введите ваш комментарий:")
            return COMMENTS
        else:
            session = self.get_session(user_id)
            session['current_order']['comments'] = None

            await query.edit_message_text(
                "💳 **Выберите способ оплаты:**",
                reply_markup=keyboards.payment_keyboard(),
                parse_mode='Markdown'
            )
            return PAYMENT

    async def process_comments_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает текст комментария"""
        user_id = update.effective_user.id
        comments = update.message.text

        session = self.get_session(user_id)
        session['current_order']['comments'] = comments

        await update.message.reply_text(
            "💳 **Выберите способ оплаты:**",
            reply_markup=keyboards.payment_keyboard(),
            parse_mode='Markdown'
        )

        return PAYMENT

    async def process_payment(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает выбор способа оплаты"""
        query = update.callback_query
        await query.answer()

        user_id = query.from_user.id
        data = query.data

        payment_methods = {
            'pay_online': 'Онлайн оплата',
            'pay_cash': 'Наличными',
            'pay_card': 'Картой при получении'
        }

        session = self.get_session(user_id)
        session['current_order']['payment_method'] = payment_methods.get(data, data)

        # Создаем заказ
        order_data = {
            'user_id': user_id,
            'total_amount': session['current_order']['total_amount'],
            'delivery_address': session['current_order']['delivery_address'],
            'delivery_time': session['current_order']['delivery_time'],
            'payment_method': session['current_order']['payment_method'],
            'phone_number': session['current_order']['phone_number'],
            'comments': session['current_order'].get('comments'),
            'items': []
        }

        # Добавляем товары
        cart_items = self.db.get_cart(user_id)
        for item in cart_items:
            order_data['items'].append({
                'product_id': item['product_id'],
                'quantity': item['quantity'],
                'price': item['price']
            })

        # Создаем заказ в базе
        order_id = self.db.create_order(order_data)

        # Формируем текст заказа
        order_text = f"""
🎉 **Заказ #{order_id} оформлен!**

📦 **Состав заказа:**
{''.join([f'• {item["name"]} x{item["quantity"]} - {item["price"] * item["quantity"]}₽\n' for item in cart_items])}

💰 **Итого:** {order_data['total_amount']}₽
📮 **Адрес:** {order_data['delivery_address']}
⏱ **Время:** {order_data['delivery_time']}
📞 **Телефон:** {order_data['phone_number']}
💳 **Оплата:** {order_data['payment_method']}
{f"💬 **Комментарий:** {order_data['comments']}" if order_data['comments'] else ""}

⏳ **Статус:** Принят в обработку
        """

        # Очищаем сессию
        self.clear_session(user_id)

        await query.edit_message_text(
            order_text,
            parse_mode='Markdown'
        )

        # Отправляем уведомление админам
        await self.notify_admins(context, order_id, order_data)

        return ConversationHandler.END

    async def notify_admins(self, context: ContextTypes.DEFAULT_TYPE, order_id: int, order_data: dict):
        """Уведомляет администраторов о новом заказе"""
        admin_text = f"""
🆕 **НОВЫЙ ЗАКАЗ #{order_id}**

👤 **Клиент:** {order_data['phone_number']}
💰 **Сумма:** {order_data['total_amount']}₽
📮 **Адрес:** {order_data['delivery_address']}
⏱ **Время:** {order_data['delivery_time']}

💳 **Оплата:** {order_data['payment_method']}
        """

        for admin_id in config.ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=admin_text,
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Failed to notify admin {admin_id}: {e}")

    async def show_orders(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает историю заказов"""
        user_id = update.effective_user.id
        orders = self.db.get_user_orders(user_id)

        if not orders:
            text = "🚚 **У вас пока нет заказов**\n\nСделайте первый заказ из меню!"
            keyboard = keyboards.InlineKeyboardMarkup([
                [keyboards.InlineKeyboardButton("📋 Перейти в меню", callback_data="back_categories")]
            ])
        else:
            total_orders = len(orders)
            total_spent = sum(order['total_amount'] for order in orders)

            text = f"🚚 **Ваши заказы**\n\n"
            text += f"📊 Всего заказов: {total_orders}\n"
            text += f"💵 Всего потрачено: {total_spent:.0f}₽\n\n"

            for order in orders[:5]:  # Показываем последние 5 заказов
                status_icon = {
                    'new': '🆕',
                    'confirmed': '✅',
                    'cooking': '👨‍🍳',
                    'delivering': '🚚',
                    'completed': '🎉',
                    'cancelled': '❌'
                }.get(order['status'], '📦')

                text += f"{status_icon} **Заказ #{order['id']}**\n"
                text += f"   💰 {order['total_amount']}₽ | 📅 {order['created_at'][:10]}\n"
                text += f"   🏠 {order['delivery_address'][:30]}...\n\n"

            if total_orders > 5:
                text += f"*... и еще {total_orders - 5} заказов*"

        if hasattr(update, 'message'):
            await update.message.reply_text(text, reply_markup=keyboards.orders_keyboard(orders), parse_mode='Markdown')
        else:
            query = update.callback_query
            await query.edit_message_text(text, reply_markup=keyboards.orders_keyboard(orders), parse_mode='Markdown')

    async def show_order_details(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает детали заказа"""
        query = update.callback_query
        await query.answer()

        order_id = int(query.data.replace('order_', ''))
        order = self.db.get_order_details(order_id)

        if not order:
            await query.edit_message_text("❌ Заказ не найден")
            return

        status_texts = {
            'new': '🆕 Принят',
            'confirmed': '✅ Подтвержден',
            'cooking': '👨‍🍳 Готовится',
            'delivering': '🚚 В пути',
            'completed': '🎉 Завершен',
            'cancelled': '❌ Отменен'
        }

        text = f"""
📦 **Заказ #{order['id']}**

📊 **Статус:** {status_texts.get(order['status'], order['status'])}
💰 **Сумма:** {order['total_amount']}₽
📮 **Адрес:** {order['delivery_address']}
⏱ **Время:** {order['delivery_time']}
📞 **Телефон:** {order['phone_number']}
💳 **Оплата:** {order['payment_method']}
📅 **Создан:** {order['created_at']}

🛒 **Состав заказа:**
"""

        for item in order['items']:
            text += f"• {item['name']} x{item['quantity']} - {item['price'] * item['quantity']}₽\n"

        if order.get('comments'):
            text += f"\n💬 **Комментарий:** {order['comments']}"

        await query.edit_message_text(text, parse_mode='Markdown')

    async def show_reviews(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает отзывы"""
        reviews = self.db.get_reviews()
        avg_rating = self.db.get_average_rating()

        text = f"⭐ **Отзывы о нашем сервисе**\n\n"
        text += f"📊 **Средний рейтинг:** {avg_rating:.1f}/5.0\n\n"

        if not reviews:
            text += "Пока нет отзывов. Будьте первым!"
        else:
            for review in reviews[:5]:
                username = review.get('first_name') or review.get('username') or 'Аноним'
                text += f"**{username}** - {review['rating']}⭐\n"
                text += f"{review['comment']}\n\n"

        keyboard = [
            [keyboards.InlineKeyboardButton("📝 Оставить отзыв", callback_data="add_review")],
            [keyboards.InlineKeyboardButton("🔙 Назад", callback_data="back_main")]
        ]

        if hasattr(update, 'message'):
            await update.message.reply_text(
                text,
                reply_markup=keyboards.InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        else:
            query = update.callback_query
            await query.edit_message_text(
                text,
                reply_markup=keyboards.InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )

    async def start_review(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начинает процесс добавления отзыва"""
        query = update.callback_query
        await query.answer()

        await query.edit_message_text(
            "⭐ **Оцените нашу работу:**\n\nПоставьте оценку от 1 до 5 звезд",
            reply_markup=keyboards.rating_keyboard(),
            parse_mode='Markdown'
        )

        return REVIEW_COMMENT

    async def process_rating(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает оценку отзыва"""
        query = update.callback_query
        await query.answer()

        rating = int(query.data.replace('rate_', ''))
        context.user_data['review_rating'] = rating

        await query.edit_message_text(
            f"📝 **Оценка: {rating}⭐**\n\nТеперь напишите ваш отзыв или комментарий:",
            parse_mode='Markdown'
        )

        return REVIEW_COMMENT

    async def process_review_comment(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает текст отзыва"""
        user_id = update.effective_user.id
        comment = update.message.text
        rating = context.user_data.get('review_rating', 5)

        # Сохраняем отзыв
        self.db.add_review(user_id, rating, comment)

        # Очищаем временные данные
        if 'review_rating' in context.user_data:
            del context.user_data['review_rating']

        await update.message.reply_text(
            "🎉 **Спасибо за ваш отзыв!**\n\nМы ценим ваше мнение и постоянно работаем над улучшением сервиса.",
            reply_markup=keyboards.main_menu(),
            parse_mode='Markdown'
        )

        return ConversationHandler.END

    async def show_premium(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает информацию о премиум подписке"""
        user_id = update.effective_user.id
        user_data = self.db.get_or_create_user(user_id)

        if user_data['is_premium']:
            status_text = "✅ **У вас активна премиум-подписка!**"
            benefits = """
🎉 **Ваши привилегии:**
• 🚀 Приоритетная доставка
• 💰 Скидка 10% на все заказы
• 🎁 Доступ к эксклюзивным товарам
• 📦 Бесплатная доставка от 1000₽
• 👑 Специальный статус
• 📊 Расширенная статистика
            """
            button_text = "🔁 Продлить подписку"
        else:
            status_text = "💎 **Премиум подписка**"
            benefits = """
✨ **Преимущества:**
• 🚀 Приоритетная доставка
• 💰 Скидка 10% на все заказы
• 🎁 Эксклюзивные товары
• 📦 Бесплатная доставка от 1000₽
• 👑 Специальный статус
• 📊 Расширенная статистика

💰 **Стоимость:** 299₽/месяц
            """
            button_text = "💎 Купить премиум"

        text = f"""
{status_text}
{benefits}
        """

        keyboard = [
            [keyboards.InlineKeyboardButton(button_text, callback_data="buy_premium")],
            [keyboards.InlineKeyboardButton("🔙 Назад", callback_data="back_main")]
        ]

        if hasattr(update, 'message'):
            await update.message.reply_text(
                text,
                reply_markup=keyboards.InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        else:
            query = update.callback_query
            await query.edit_message_text(
                text,
                reply_markup=keyboards.InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )

    async def buy_premium(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает покупку премиум подписки"""
        query = update.callback_query
        await query.answer()

        user_id = query.from_user.id
        user_data = self.db.get_or_create_user(user_id)

        if user_data['is_premium']:
            await query.edit_message_text(
                "✅ У вас уже есть активная премиум подписка!",
                parse_mode='Markdown'
            )
            return

        # В реальном приложении здесь была бы интеграция с платежной системой
        # Для демо просто активируем премиум
        self.db.set_premium(user_id, True)

        await query.edit_message_text(
            f"""
🎉 **Поздравляем с покупкой премиум подписки!**

Теперь вам доступны все эксклюзивные возможности:

• 🚀 Приоритетная доставка
• 💰 Скидка 10% на все заказы  
• 🎁 Доступ к эксклюзивным товарам
• 📦 Бесплатная доставка от 1000₽
• 👑 Специальный статус

Спасибо за доверие! Ваша поддержка помогает нам становиться лучше 💫
            """,
            parse_mode='Markdown'
        )

    async def show_promotions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает акции и промокоды"""
        text = """
🎁 **Акции и промокоды**

🔥 **Горячие предложения:**
• 🍕 Пицца дня всего 399₽
• ☕ Кофе + десерт = 350₽
• 🚚 Бесплатная доставка от 1500₽

🎫 **Промокоды:**
• WELCOME10 - 10% скидка на первый заказ
• FIRSTORDER - 15% скидка на заказ от 1000₽
• PREMIUM20 - 20% скидка для премиум пользователей

💎 **Премиум подписка** дает дополнительные 10% скидку на все заказы!
        """

        if hasattr(update, 'message'):
            await update.message.reply_text(
                text,
                reply_markup=keyboards.promo_keyboard(),
                parse_mode='Markdown'
            )
        else:
            query = update.callback_query
            await query.edit_message_text(
                text,
                reply_markup=keyboards.promo_keyboard(),
                parse_mode='Markdown'
            )

    async def apply_promo_code(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Применяет промокод с кнопкой назад"""
        query = update.callback_query
        await query.answer()

        user_id = query.from_user.id

        if query.data == 'enter_promo':
            # Создаем клавиатуру с кнопкой назад
            keyboard = [
                [keyboards.InlineKeyboardButton("🔙 Назад", callback_data="back_promo")]
            ]

            await query.edit_message_text(
                "🎫 **Введите промокод:**\n\nИли нажмите 'Назад' для возврата:",
                reply_markup=keyboards.InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            return PROMO_CODE
        elif query.data == 'list_promos':
            await self.show_promotions(update, context)
            return ConversationHandler.END

    async def process_promo_code(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает введенный промокод"""
        user_id = update.effective_user.id
        promo_code = update.message.text.upper()

        promo = self.db.get_promo_code(promo_code)

        if not promo:
            await update.message.reply_text(
                "❌ **Промокод не найден или не активен**\n\nПопробуйте другой промокод или введите заново:",
                parse_mode='Markdown'
            )
            return PROMO_CODE

        # Проверяем лимит использования
        if promo['usage_limit'] > 0 and promo['used_count'] >= promo['usage_limit']:
            await update.message.reply_text(
                "❌ **Промокод уже использован максимальное количество раз**\n\nПопробуйте другой промокод:",
                parse_mode='Markdown'
            )
            return PROMO_CODE

        # Проверяем минимальную сумму заказа
        cart_items = self.db.get_cart(user_id)
        cart_total = sum(item['price'] * item['quantity'] for item in cart_items)

        if cart_total < promo['min_order_amount']:
            await update.message.reply_text(
                f"❌ **Промокод действует для заказов от {promo['min_order_amount']}₽**\n\nВаша корзина: {cart_total}₽\n\nПопробуйте другой промокод:",
                parse_mode='Markdown'
            )
            return PROMO_CODE

        # Применяем промокод
        session = self.get_session(user_id)
        session['promo_code'] = promo_code
        session['promo_discount'] = promo['discount_percent']

        # Используем промокод
        self.db.use_promo_code(promo_code)

        discount_text = f"{promo['discount_percent']}%"
        if promo['discount_amount'] > 0:
            discount_text = f"{promo['discount_amount']}₽"

        await update.message.reply_text(
            f"✅ **Промокод активирован!**\n\nСкидка: {discount_text}\n\nТеперь перейдите в корзину для оформления заказа.",
            reply_markup=keyboards.main_menu(),
            parse_mode='Markdown'
        )

        return ConversationHandler.END

    async def show_support(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает раздел поддержки"""
        text = """
📞 **Поддержка**

💬 **Чат с оператором:** @your_support_bot
📞 **Телефон:** +7 (XXX) XXX-XX-XX
🕒 **Время работы:** 9:00 - 23:00

📧 **Email:** support@yourshop.ru

💡 **Частые вопросы:**
• 🕒 Время доставки: 30-60 минут
• 💰 Минимальный заказ: 500₽
• 🚚 Бесплатная доставка: от 1500₽
• 🔄 Возврат: в течение 2 часов

Напишите ваш вопрос, и мы обязательно поможем!
        """

        await update.message.reply_text(text, parse_mode='Markdown')

    async def show_about(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает информацию о компании"""
        text = """
ℹ️ **О нас**

🍕 **Ваш любимый сервис доставки еды!**

Мы работаем с 2020 года и доставили уже более 100,000 заказов.

🌟 **Наши преимущества:**
• 🚀 Быстрая доставка за 30-60 минут
• 🍔 Свежие продукты и качественная готовка
• 💰 Доступные цены и регулярные акции
• 👨‍🍳 Профессиональные повара
• 📞 Круглосуточная поддержка

🏆 **Награды:**
• Лучший сервис доставки 2023
• Выбор покупателей 2024

📍 **Наши рестораны:**
• ул. Центральная, 1
• пр. Мира, 15
• б-р. Строителей, 8

Спасибо, что выбираете нас! ❤️
        """

        await update.message.reply_text(text, parse_mode='Markdown')

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает текстовые сообщения"""
        user_message = update.message.text

        if user_message == "📋 Меню":
            await self.show_menu(update, context)
        elif user_message == "🛒 Корзина":
            await self.show_cart(update, context)
        elif user_message == "🚚 Мои заказы":
            await self.show_orders(update, context)
        elif user_message == "⭐ Отзывы":
            await self.show_reviews(update, context)
        elif user_message == "💎 Премиум":
            await self.show_premium(update, context)
        elif user_message == "🎁 Акции":
            await self.show_promotions(update, context)
        elif user_message == "🎯 Рекомендации":
            await self.show_recommendations(update, context)
        elif user_message == "🏆 Лояльность":
            await self.show_loyalty(update, context)
        elif user_message == "🔄 Повтор заказа":
            await self.quick_reorder(update, context)
        elif user_message == "📞 Поддержка":
            await self.show_support(update, context)
        else:
            await update.message.reply_text(
                "🤔 Не понял ваше сообщение. Используйте кнопки меню для навигации.",
                reply_markup=keyboards.main_menu()
            )

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает callback запросы"""
        query = update.callback_query
        await query.answer()

        data = query.data

        try:
            # НАВИГАЦИЯ - исправленные и добавленные back-кнопки
            if data == 'back_main':
                await query.edit_message_text(
                    "Возвращаюсь в главное меню...",
                    reply_markup=keyboards.main_menu()
                )
            elif data == 'back_categories':
                await self.show_menu(update, context)
            elif data == 'back_products':
                categories = self.db.get_categories()
                await query.edit_message_text(
                    "📋 **Выберите категорию:**",
                    reply_markup=keyboards.categories_keyboard(categories),
                    parse_mode='Markdown'
                )
            elif data == 'back_cart':
                await self.show_cart(update, context)
            elif data == 'back_promo':
                await self.show_promotions(update, context)

            # ОСНОВНЫЕ РАЗДЕЛЫ
            elif data == 'popular':
                await self.show_popular(update, context)
            elif data.startswith('cat_'):
                await self.show_category(update, context)
            elif data.startswith('prod_'):
                await self.show_product(update, context)
            elif data.startswith(('add_', 'inc_', 'dec_', 'cart_inc_', 'cart_dec_', 'cart_del_')):
                await self.update_cart_quantity(update, context)
            elif data == 'clear_cart':
                await self.clear_cart(update, context)
            elif data == 'apply_promo':
                await self.apply_promo_code(update, context)
            elif data == 'list_promos':
                await self.show_promotions(update, context)
            elif data.startswith('order_'):
                await self.show_order_details(update, context)
            elif data == 'add_review':
                await self.start_review(update, context)
            elif data == 'buy_premium':
                await self.buy_premium(update, context)

            # НОВЫЕ ФУНКЦИИ - добавляем обработку
            elif data == 'show_recommendations':
                await self.show_recommendations(update, context)
            elif data == 'show_loyalty':
                await self.show_loyalty(update, context)
            elif data == 'quick_reorder':
                await self.quick_reorder(update, context)

            else:
                await query.edit_message_text("❌ Неизвестная команда")

        except Exception as e:
            logger.error(f"Error in callback handler: {e}")
            await query.edit_message_text("❌ Произошла ошибка. Попробуйте еще раз.")

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отменяет текущий процесс"""
        await update.message.reply_text(
            "❌ Процесс отменен.",
            reply_markup=keyboards.main_menu()
        )
        return ConversationHandler.END


async def notify_order_status(self, user_id: int, order_id: int, status: str, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет уведомление об изменении статуса заказа"""
    status_messages = {
        'confirmed': '✅ Ваш заказ подтвержден и готовится!',
        'cooking': '👨‍🍳 Ваш заказ готовится!',
        'delivering': '🚚 Ваш заказ в пути!',
        'completed': '🎉 Заказ доставлен! Спасибо за покупку!',
        'cancelled': '❌ Заказ отменен.'
    }

    message = status_messages.get(status, f'Статус заказа изменен: {status}')

    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"📦 Заказ #{order_id}\n\n{message}",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Failed to send status notification: {e}")

        async def search_products(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
            """Поиск товаров по названию"""
            if not context.args:
                await update.message.reply_text(
                    "🔍 **Поиск товаров**\n\nВведите название товара после команды /search\nНапример: /search пицца",
                    parse_mode='Markdown'
                )
                return

            search_query = ' '.join(context.args).lower()
            conn = self.db.get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT * FROM products 
                WHERE (LOWER(name) LIKE ? OR LOWER(description) LIKE ?) 
                AND is_available = TRUE
                LIMIT 10
            ''', (f'%{search_query}%', f'%{search_query}%'))

            products = [dict(row) for row in cursor.fetchall()]
            conn.close()

            if not products:
                await update.message.reply_text(
                    f"😔 По запросу '{search_query}' ничего не найдено.",
                    parse_mode='Markdown'
                )
                return

            text = f"🔍 **Результаты поиска '{search_query}':**\n\n"
            for product in products:
                text += f"• {product['name']} - {product['price']}₽\n"
                text += f"  _{product['description']}_\n\n"

            keyboard = []
            for product in products:
                keyboard.append([InlineKeyboardButton(
                    f"{product['name']} - {product['price']}₽",
                    callback_data=f"prod_{product['id']}"
                )])

            keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_main")])

            await update.message.reply_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
def main():
    """Запускает бота"""
    shop_bot = ShopBot()


    # Создаем приложение
    application = Application.builder().token(config.BOT_TOKEN).build()

    # ConversationHandler для оформления заказа
    order_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(shop_bot.start_checkout, pattern='^checkout$')],
        states={
            ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, shop_bot.process_address)],
            DELIVERY_TIME: [
                CallbackQueryHandler(shop_bot.process_delivery_time, pattern='^time_'),
                MessageHandler(filters.TEXT & ~filters.COMMAND, shop_bot.process_delivery_time)
            ],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, shop_bot.process_phone)],
            COMMENTS: [
                CallbackQueryHandler(shop_bot.process_comments, pattern='^(yes|no)$'),
                MessageHandler(filters.TEXT & ~filters.COMMAND, shop_bot.process_comments_text)
            ],
            PAYMENT: [CallbackQueryHandler(shop_bot.process_payment, pattern='^pay_')],
        },
        fallbacks=[CommandHandler('cancel', shop_bot.cancel)]
    )

    # ConversationHandler для отзывов
    review_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(shop_bot.start_review, pattern='^add_review$')],
        states={
            REVIEW_COMMENT: [
                CallbackQueryHandler(shop_bot.process_rating, pattern='^rate_'),
                MessageHandler(filters.TEXT & ~filters.COMMAND, shop_bot.process_review_comment)
            ],
        },
        fallbacks=[CommandHandler('cancel', shop_bot.cancel)]
    )

    # ConversationHandler для промокодов
    promo_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(shop_bot.apply_promo_code, pattern='^enter_promo$')],
        states={
            PROMO_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, shop_bot.process_promo_code)],
        },
        fallbacks=[CommandHandler('cancel', shop_bot.cancel)]
    )

    # Добавляем обработчики
    application.add_handler(CommandHandler("start", shop_bot.start))
    application.add_handler(order_conv_handler)
    application.add_handler(review_conv_handler)
    application.add_handler(promo_conv_handler)
    application.add_handler(CallbackQueryHandler(shop_bot.handle_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, shop_bot.handle_message))

    # Запускаем бота
    print("🍕 Бот запущен! Ожидаем заказов...")
    application.run_polling()


if __name__ == '__main__':
    main()
from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
import config


def main_menu():
    return ReplyKeyboardMarkup([
        ["📋 Меню", "🛒 Корзина"],
        ["🚚 Мои заказы", "⭐ Отзывы"],
        ["💎 Премиум", "🎁 Акции"],
        ["🎯 Рекомендации", "🏆 Лояльность"],
        ["🔄 Повтор заказа", "📞 Поддержка"]
    ], resize_keyboard=True)


def categories_keyboard(categories):
    keyboard = []
    row = []

    for i, category in enumerate(categories):
        emoji = config.CATEGORIES.get(category, '📦')
        row.append(InlineKeyboardButton(
            f"{emoji} {config.CATEGORIES.get(category, category)}",
            callback_data=f"cat_{category}"
        ))

        if len(row) == 2 or i == len(categories) - 1:
            keyboard.append(row)
            row = []

    keyboard.append([InlineKeyboardButton("🔍 Популярные товары", callback_data="popular")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_main")])

    return InlineKeyboardMarkup(keyboard)


def products_keyboard(products, back_to="categories"):
    keyboard = []

    for product in products:
        keyboard.append([
            InlineKeyboardButton(
                f"{product['name']} - {product['price']}₽",
                callback_data=f"prod_{product['id']}"
            )
        ])

    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data=f"back_{back_to}")])
    return InlineKeyboardMarkup(keyboard)


def product_keyboard(product_id, in_cart=False):
    keyboard = [
        [
            InlineKeyboardButton("➖", callback_data=f"dec_{product_id}"),
            InlineKeyboardButton("➕", callback_data=f"inc_{product_id}"),
        ],
        [
            InlineKeyboardButton("🛒 В корзину", callback_data=f"add_{product_id}"),
        ] if not in_cart else [
            InlineKeyboardButton("✅ В корзине", callback_data=f"already_{product_id}"),
        ],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_products")]
    ]
    return InlineKeyboardMarkup(keyboard)


def cart_keyboard(cart_items, can_order=True):
    keyboard = []

    for item in cart_items:
        keyboard.extend([
            [
                InlineKeyboardButton(f"➖ {item['name']}", callback_data=f"cart_dec_{item['product_id']}"),
                InlineKeyboardButton(f"➕", callback_data=f"cart_inc_{item['product_id']}"),
            ],
            [InlineKeyboardButton(f"❌ Удалить {item['name']}", callback_data=f"cart_del_{item['product_id']}")]
        ])

    if cart_items:
        if can_order:
            keyboard.append([InlineKeyboardButton("🚚 Оформить заказ", callback_data="checkout")])
        keyboard.append([InlineKeyboardButton("🎁 Применить промокод", callback_data="apply_promo")])
        keyboard.append([InlineKeyboardButton("🗑 Очистить корзину", callback_data="clear_cart")])

    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(keyboard)


def delivery_time_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⏱ Как можно скорее", callback_data="time_asap")],
        [InlineKeyboardButton("🕐 В течение часа", callback_data="time_1h")],
        [InlineKeyboardButton("🕑 Через 2 часа", callback_data="time_2h")],
        [InlineKeyboardButton("🕒 Указать своё время", callback_data="time_custom")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_cart")]
    ])


def payment_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Онлайн оплата", callback_data="pay_online")],
        [InlineKeyboardButton("💵 Наличными при получении", callback_data="pay_cash")],
        [InlineKeyboardButton("💳 Картой при получении", callback_data="pay_card")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_delivery")]
    ])


def rating_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("1 ⭐", callback_data="rate_1"),
            InlineKeyboardButton("2 ⭐", callback_data="rate_2"),
            InlineKeyboardButton("3 ⭐", callback_data="rate_3"),
            InlineKeyboardButton("4 ⭐", callback_data="rate_4"),
            InlineKeyboardButton("5 ⭐", callback_data="rate_5"),
        ],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_main")]
    ])


def orders_keyboard(orders):
    keyboard = []
    for order in orders[:5]:  # Показываем последние 5 заказов
        status_icon = {
            'new': '🆕',
            'confirmed': '✅',
            'cooking': '👨‍🍳',
            'delivering': '🚚',
            'completed': '🎉',
            'cancelled': '❌'
        }.get(order['status'], '📦')

        keyboard.append([
            InlineKeyboardButton(
                f"{status_icon} Заказ #{order['id']} - {order['total_amount']}₽",
                callback_data=f"order_{order['id']}"
            )
        ])

    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(keyboard)


def promo_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎁 Применить промокод", callback_data="enter_promo")],
        [InlineKeyboardButton("📜 Активные промокоды", callback_data="list_promos")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_main")]
    ])


def yes_no_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Да", callback_data="yes"), ],
        [InlineKeyboardButton("❌ Нет", callback_data="no")]
    ])


def admin_keyboard():
    return ReplyKeyboardMarkup([
        ["📊 Статистика", "📦 Заказы"],
        ["🎁 Управление промокодами", "📢 Рассылка"],
        ["🔙 В главное меню"]
    ], resize_keyboard=True)


def back_button_only():
    """Просто кнопка назад"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Назад", callback_data="back_main")]
    ])


def promo_with_back():
    """Клавиатура для промокодов с кнопкой назад"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎁 Применить промокод", callback_data="enter_promo")],
        [InlineKeyboardButton("📜 Активные промокоды", callback_data="list_promos")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_main")]
    ])


def categories_with_back():
    """Категории с улучшенной навигацией"""
    categories = ["pizza", "burger", "sushi", "drink", "dessert", "salad"]
    keyboard = []
    row = []

    for i, category in enumerate(categories):
        emoji = config.CATEGORIES.get(category, '📦')
        row.append(InlineKeyboardButton(
            f"{emoji}",
            callback_data=f"cat_{category}"
        ))

        if len(row) == 3 or i == len(categories) - 1:
            keyboard.append(row)
            row = []

    keyboard.append([InlineKeyboardButton("🔍 Популярные товары", callback_data="popular")])
    keyboard.append([InlineKeyboardButton("🔙 В главное меню", callback_data="back_main")])

    return InlineKeyboardMarkup(keyboard)
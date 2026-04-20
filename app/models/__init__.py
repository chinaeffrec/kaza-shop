# Порядок важен: сначала модели без зависимостей, потом те что ссылаются на них
from app.models.user import User
from app.models.subcategory import SubCategory   # SubCategory до Category (category.py использует relationship на SubCategory)
from app.models.category import Category
from app.models.product import Product
from app.models.cart import Cart
from app.models.order import Order, OrderItem

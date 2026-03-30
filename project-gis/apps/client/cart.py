from decimal import Decimal
from django.conf import settings
from apps.core.models import Product

class Cart:
    def __init__(self, request):
        """Khởi tạo giỏ hàng"""
        self.session = request.session
        cart = self.session.get('session_key_cart')
        if not cart:
            # Lưu giỏ hàng trống vào session
            cart = self.session['session_key_cart'] = {}
        self.cart = cart

    def add(self, product, quantity=1):
        """Thêm sản phẩm vào giỏ hoặc cập nhật số lượng"""
        product_id = str(product.id)
        if product_id not in self.cart:
            self.cart[product_id] = {'quantity': 0, 'price': str(product.price)}
        
        self.cart[product_id]['quantity'] += quantity
        self.save()

    def remove(self, product):
        """Xóa sản phẩm khỏi giỏ"""
        product_id = str(product.id)
        if product_id in self.cart:
            del self.cart[product_id]
            self.save()

    def save(self):
        """Đánh dấu session đã thay đổi để Django lưu lại"""
        self.session.modified = True

    def __iter__(self):
        """Lặp qua các sản phẩm trong giỏ để hiển thị ra template"""
        product_ids = self.cart.keys()
        products = Product.objects.filter(id__in=product_ids)
        
        cart_copy = self.cart.copy()
        for product in products:
            cart_copy[str(product.id)]['product'] = product

        for item in cart_copy.values():
            item['price'] = Decimal(item['price'])
            item['total_price'] = item['price'] * item['quantity']
            yield item

    def get_total_price(self):
        """Tính tổng tiền cả giỏ hàng"""
        return sum(Decimal(item['price']) * item['quantity'] for item in self.cart.values())

    def clear(self):
        """Xóa sạch giỏ hàng"""
        del self.session['session_key_cart']
        self.save()
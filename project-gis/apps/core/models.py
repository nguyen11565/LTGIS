from django.db import models
from django.contrib.auth.models import User
# ==========================================
# 1. PHẦN CŨ (GIỮ NGUYÊN)
# ==========================================

# Bảng Danh mục sản phẩm
class Category(models.Model):
    name = models.CharField(max_length=100, verbose_name="Tên danh mục")
    slug = models.SlugField(unique=True)

    def __str__(self):
        return self.name

# Bảng Sản phẩm điện thoại
class Product(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    name = models.CharField(max_length=200, verbose_name="Tên điện thoại")
    price = models.DecimalField(max_digits=12, decimal_places=0, verbose_name="Giá bán")
    description = models.TextField(verbose_name="Mô tả chi tiết")
    image = models.ImageField(upload_to='products/', null=True, blank=True)
    stock = models.IntegerField(default=0, verbose_name="Số lượng kho")
    created_at = models.DateTimeField(auto_now_add=True)
    content = models.TextField(null=True, blank=True, verbose_name="Bài viết giới thiệu")

    def __str__(self):
        return self.name
    
class ProductImage(models.Model):
        product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
        image = models.ImageField(upload_to='products/gallery/')

        def __str__(self):
            return f"Image for {self.product.name}"

# ==========================================
# 2. PHẦN MỚI THÊM VÀO (CHO GIS/BẢN ĐỒ)
# ==========================================

class Store(models.Model):
    name = models.CharField(max_length=100, verbose_name="Tên cửa hàng")
    address = models.CharField(max_length=255, verbose_name="Địa chỉ")
    phone = models.CharField(max_length=20, verbose_name="Hotline")
    image = models.ImageField(upload_to='stores/', null=True, blank=True, verbose_name="Hình ảnh cửa hàng")
    # Lưu tọa độ bằng số thực (Float) để dùng công thức Haversine
    # Ví dụ: Hà Nội (Lat: 21.0285, Lon: 105.8542)
    latitude = models.FloatField(verbose_name="Vĩ độ (Lat)")
    longitude = models.FloatField(verbose_name="Kinh độ (Lon)")

    def __str__(self):
        return self.name
    
    # ... (Giữ nguyên code Store, Product, Category cũ)

class Order(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Chờ xử lý'),
        ('processing', 'Đang đóng gói'),
        ('shipped', 'Đang giao hàng'),
        ('completed', 'Hoàn thành'),
        ('cancelled', 'Đã hủy'),
    )
    # ... các trường khác ...
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders', null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    full_name = models.CharField(max_length=100, verbose_name="Họ và tên")
    address = models.CharField(max_length=255, verbose_name="Địa chỉ giao hàng")
    phone = models.CharField(max_length=20, verbose_name="Số điện thoại")
    total_price = models.DecimalField(max_digits=12, decimal_places=0, verbose_name="Tổng tiền")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Ngày đặt")

    def __str__(self):
        return f"Đơn hàng #{self.id} - {self.full_name}"

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=12, decimal_places=0)
    quantity = models.IntegerField(default=1)

    def __str__(self):
        return f"{self.product.name} (x{self.quantity})"
    

class Stores(models.Model):
    name = models.CharField(max_length=200)
    address = models.CharField(max_length=500)
    latitude = models.FloatField()
    longitude = models.FloatField()
    # Thêm 2 dòng này:
    opening_time = models.TimeField(default="08:00:00")
    closing_time = models.TimeField(default="21:00:00")

    def __str__(self):
        return self.name
    
from django.contrib.auth.models import User # Đảm bảo có dòng này ở đầu file models.py

class StockTransaction(models.Model):
    TRANSACTION_TYPES = (
        ('in', 'Nhập kho'),
        ('out', 'Xuất kho'),
    )

    # Kết nối với sản phẩm
    product = models.ForeignKey(
        'Product', 
        on_delete=models.CASCADE, 
        related_name='stock_history',
        verbose_name="Sản phẩm"
    )
    
    # Số lượng và loại giao dịch
    quantity = models.IntegerField(verbose_name="Số lượng thay đổi")
    transaction_type = models.CharField(
        max_length=3, 
        choices=TRANSACTION_TYPES, 
        verbose_name="Loại giao dịch"
    )

    # --- CÁC TRƯỜNG BỔ SUNG MỚI ---
    # 1. Giá nhập (Chỉ dùng khi transaction_type == 'in')
    price = models.DecimalField(
        max_digits=12, 
        decimal_places=0, 
        default=0, 
        verbose_name="Giá nhập đơn vị"
    )

    # 2. Cửa hàng đích (Chỉ dùng khi transaction_type == 'out')
    store_destination = models.ForeignKey(
        'Store', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name="Cửa hàng nhận"
    )
    # ------------------------------
    
    # Thông tin bổ sung
    note = models.TextField(blank=True, null=True, verbose_name="Ghi chú/Lý do")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Thời gian thực hiện")
    
    # Người thực hiện
    user = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        verbose_name="Người thực hiện"
    )

    def __str__(self):
        return f"{self.get_transaction_type_display()} - {self.product.name} ({self.quantity})"

    # Hàm tính tổng tiền giao dịch (dùng cho nhật ký)
    def get_total_value(self):
        return self.quantity * self.price

    class Meta:
        verbose_name = "Giao dịch kho"
        verbose_name_plural = "Danh sách giao dịch kho"

    class Meta:
        verbose_name = "Giao dịch kho"
        verbose_name_plural = "Lịch sử giao dịch kho"
        ordering = ['-created_at'] # Luôn hiện giao dịch mới nhất lên đầu

    def __str__(self):
        return f"{self.get_transaction_type_display()} - {self.product.name} ({self.quantity})"
    

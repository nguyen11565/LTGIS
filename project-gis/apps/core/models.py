from django.db import models

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

    def __str__(self):
        return self.name

# ==========================================
# 2. PHẦN MỚI THÊM VÀO (CHO GIS/BẢN ĐỒ)
# ==========================================

class Store(models.Model):
    name = models.CharField(max_length=100, verbose_name="Tên cửa hàng")
    address = models.CharField(max_length=255, verbose_name="Địa chỉ")
    phone = models.CharField(max_length=20, verbose_name="Hotline")
    
    # Lưu tọa độ bằng số thực (Float) để dùng công thức Haversine
    # Ví dụ: Hà Nội (Lat: 21.0285, Lon: 105.8542)
    latitude = models.FloatField(verbose_name="Vĩ độ (Lat)")
    longitude = models.FloatField(verbose_name="Kinh độ (Lon)")

    def __str__(self):
        return self.name
    
    # ... (Giữ nguyên code Store, Product, Category cũ)

class Order(models.Model):
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
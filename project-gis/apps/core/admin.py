from django.contrib import admin
from .models import Category, Product, Store # <-- Nhớ import Store ở đây

# Đăng ký bảng Danh mục
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}

# Đăng ký bảng Sản phẩm
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'price', 'stock', 'category']
    list_filter = ['category']
    search_fields = ['name']

# --- PHẦN MỚI THÊM VÀO ---
# Đăng ký bảng Cửa hàng (Store)
@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    # Hiển thị các cột này ra danh sách
    list_display = ['name', 'address', 'phone', 'latitude', 'longitude']
    # Cho phép tìm kiếm theo tên và địa chỉ
    search_fields = ['name', 'address']
from django.contrib import admin
from .models import Category, Product, Store, StoreStock, Notification


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

@admin.register(StoreStock)
class StoreStockAdmin(admin.ModelAdmin):
    # Các cột sẽ hiển thị ra ngoài bảng
    list_display = ('store', 'product', 'quantity')
    
    # Tạo bộ lọc bên phải để dễ tìm theo cửa hàng
    list_filter = ('store',)
    
    # Thanh tìm kiếm theo tên sản phẩm
    search_fields = ('product__name',)

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'notif_type', 'order', 'is_read', 'created_at')
    list_filter  = ('notif_type', 'is_read')
    search_fields = ('user__username', 'message')
    ordering = ('-created_at',)
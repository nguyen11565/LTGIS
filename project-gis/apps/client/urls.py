from django.urls import path
from . import views

app_name = 'client'

urlpatterns = [
    # Trang chủ
    path('', views.home, name='home'),
    
    # Giỏ hàng (Sửa views.cart thành views.cart_detail)
    path('cart/', views.cart_detail, name='cart'), 
    
    # Thêm/Xóa sản phẩm
    path('add/<int:product_id>/', views.cart_add, name='cart_add'),
    path('remove/<int:product_id>/', views.cart_remove, name='cart_remove'),

    # Bản đồ tìm cửa hàng (Thêm dòng này nếu chưa có)
    path('store-locator/', views.store_locator, name='store_locator'),
    
    # Link chi tiết sản phẩm
    path('product/<int:product_id>/', views.product_detail, name='product_detail'),
    
    # Link thanh toán
    path('checkout/', views.checkout, name='checkout'),
]
from django.urls import path
from . import views
from . import views_admin
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

    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    # đơn hàng
    path('my-orders/', views.my_orders, name='my_orders'),
    #tim kiem san pham
    path('search/', views.search_view, name='search'),

    # ĐƯỜNG DẪN ADMIN
    path('my-admin/', views_admin.dashboard, name='admin_dashboard'),
    path('my-admin/stores/', views_admin.store_list, name='admin_store_list'),
    path('my-admin/stores/add/', views_admin.store_add, name='admin_store_add'),
    path('my-admin/stores/edit/<int:pk>/', views_admin.store_edit, name='admin_store_edit'),
    path('my-admin/stores/delete/<int:pk>/', views_admin.store_delete, name='admin_store_delete'),

    # QUẢN LÝ SẢN PHẨM
    path('my-admin/products/', views_admin.product_list, name='admin_product_list'),
    path('my-admin/products/add/', views_admin.product_add, name='admin_product_add'),
    path('my-admin/products/edit/<int:pk>/', views_admin.product_edit, name='admin_product_edit'),
    path('my-admin/products/delete/<int:pk>/', views_admin.product_delete, name='admin_product_delete'),
    path('my-admin/categories/edit/<int:pk>/', views_admin.category_edit, name='admin_category_edit'),
    path('my-admin/categories/delete/<int:pk>/', views_admin.category_delete, name='admin_category_delete'),

    # QUẢN LÝ ĐƠN HÀNG
    path('my-admin/orders/', views_admin.order_list, name='admin_order_list'),
    path('my-admin/orders/<int:pk>/', views_admin.order_detail, name='admin_order_detail'),
]
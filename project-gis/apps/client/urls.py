from django.urls import path
from . import views
from . import views_admin
from django.conf.urls import handler404
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
    path('api/store-stock/', views.api_search_stock, name='api_search_stock'),
    
    # Link chi tiết sản phẩm
    path('product/<int:product_id>/', views.product_detail, name='product_detail'),
    
    # Link thanh toán
    path('checkout/', views.checkout, name='checkout'),
    path('checkout/payment/<int:order_id>/', views.payment_instruction_view, name='payment_instruction'),

    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    # Xác thực email
    path('verify-email/<uidb64>/<token>/', views.verify_email, name='verify_email'),
    path('verification-pending/', views.verification_pending, name='verification_pending'),
    path('resend-verification/', views.resend_verification, name='resend_verification'),
    # Quên mật khẩu
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('reset-password/<uidb64>/<token>/', views.reset_password, name='reset_password'),
    # đơn hàng
    path('my-orders/', views.my_orders, name='my_orders'),
    #tim kiem san pham
    path('search/', views.search_view, name='search'),
    path('api/search-autocomplete/', views.api_search_autocomplete, name='api_search_autocomplete'),
    path('my-orders/<int:order_id>/', views.order_detail, name='order_detail'),
    path('my-orders/<int:order_id>/receipt/', views.client_print_receipt, name='client_print_receipt'),
    path('my-orders/cancel/<int:order_id>/', views.cancel_order, name='cancel_order'),

    # Yêu cầu trả hàng
    path('my-orders/<int:order_id>/request-return/', views.request_return_view, name='request_return'),
    path('account/return-history/', views.return_history_view, name='return_history'),
    # ĐƯỜNG DẪN ADMIN
    path('my-admin/', views_admin.dashboard, name='admin_dashboard'),
    path('my-admin/stores/', views_admin.store_list, name='admin_store_list'),
    path('my-admin/stores/add/', views_admin.store_add, name='admin_store_add'),
    path('my-admin/stores/edit/<int:pk>/', views_admin.store_edit, name='admin_store_edit'),
    path('my-admin/stores/delete/<int:pk>/', views_admin.store_delete, name='admin_store_delete'),
    path('my-admin/stock/', views_admin.admin_stock_management, name='admin_stock_management'),
    path('my-admin/stock/create/<str:t_type>/', views_admin.stock_transaction_create, name='admin_stock_transaction_create'),
    path('my-admin/stock/print/<int:transaction_id>/', views_admin.print_stock_transaction, name='print_stock'),
    path('my-admin/stores/<int:store_id>/', views_admin.store_detail, name='admin_store_detail'),

    # QUẢN LÝ KHU VỰC
    path('my-admin/regions/', views_admin.region_list, name='admin_region_list'),
    path('my-admin/regions/add/', views_admin.region_add, name='admin_region_add'),
    path('my-admin/regions/edit/<int:pk>/', views_admin.region_edit, name='admin_region_edit'),
    path('my-admin/regions/delete/<int:pk>/', views_admin.region_delete, name='admin_region_delete'),

    # QUẢN LÝ ĐIỀU CHUYỂN KHO
    path('my-admin/transfers/', views_admin.transfer_list, name='admin_transfer_list'),
    path('my-admin/transfers/create/', views_admin.transfer_create, name='admin_transfer_create'),
    path('my-admin/transfers/<int:pk>/', views_admin.transfer_detail, name='admin_transfer_detail'),
    path('my-admin/transfers/<int:pk>/action/', views_admin.transfer_action, name='admin_transfer_action'),

    # QUẢN LÝ KIỂM KÊ KHO
    path('my-admin/stocktaking/', views_admin.stocktaking_list, name='admin_stocktaking_list'),
    path('my-admin/stocktaking/create/', views_admin.stocktaking_create, name='admin_stocktaking_create'),
    path('my-admin/stocktaking/<int:pk>/', views_admin.stocktaking_detail, name='admin_stocktaking_detail'),
    path('my-admin/stocktaking/<int:pk>/action/', views_admin.stocktaking_action, name='admin_stocktaking_action'),

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
    path('my-admin/orders/print-invoice/<int:pk>/', views_admin.print_invoice_view, name='print_invoice'),
    path('cart/update/<int:product_id>/<int:quantity>/', views.cart_update, name='cart_update'),

    # QUẢN LÝ TRẢ HÀNG
    path('my-admin/returns/', views_admin.admin_return_list, name='admin_return_list'),
    path('my-admin/returns/<int:pk>/', views_admin.admin_return_detail, name='admin_return_detail'),

    # QUẢN LÝ NHÂN SỰ
    path('my-admin/employees/', views_admin.admin_employee_list, name='admin_employee_list'),

    # Sale
    path('my-admin/flash-sales/', views_admin.admin_flash_sale, name='admin_flash_sale'),
    path('my-admin/flash-sales/delete/<int:pk>/', views_admin.delete_flash_sale, name='delete_flash_sale'),


    #voucher
    path('my-admin/coupons/', views_admin.admin_coupon_list, name='admin_coupon_list'),
    path('my-admin/coupons/delete/<int:pk>/', views_admin.admin_coupon_delete, name='admin_coupon_delete'),

    #user voucher
    path('apply-coupon/', views.apply_coupon, name='apply_coupon'),
    path('remove-coupon/', views.remove_coupon, name='remove_coupon'),

    #tài khoản
    path('account/', views.user_account, name='user_account'),

    # Ý kiến khách hàng
    path('feedback/', views.feedback_view, name='feedback'),

    # Thông báo đơn hàng
    path('notifications/', views.notifications_list, name='notifications'),
    path('notifications/read/<int:pk>/', views.mark_notification_read, name='mark_notification_read'),
    path('notifications/read-all/', views.mark_all_notifications_read, name='mark_all_notifications_read'),

    #nhập/xuất excel (admin)
    path('my-admin/export-products/', views_admin.export_products_excel, name='export_excel'),
    path('my-admin/import-products/', views_admin.import_products_excel, name='import_excel'),
    path('my-admin/export-orders/', views_admin.export_orders_excel, name='export_orders_excel'),
    path('my-admin/export-monthly-revenue/', views_admin.export_monthly_revenue_excel, name='export_monthly_revenue'),
    path('my-admin/download-template/', views_admin.download_product_template, name='download_template'),

    # Trang chính sách
    path('chinh-sach-bao-hanh/', views.policy_warranty, name='policy_warranty'),
    path('chinh-sach-doi-tra/', views.policy_return, name='policy_return'),
    path('huong-dan-mua-hang/', views.policy_guide, name='policy_guide'),

    # API Chat AI
    path('api/ai-chat/', views.ai_chat_api, name='ai_chat_api'),

    # ==========================
    # URL TIN TỨC (NEWS)
    # ==========================
    # Client News
    path('tin-tuc/', views.news_list, name='news_list'),
    path('tin-tuc/<slug:slug>/', views.news_detail, name='news_detail'),

    # Admin News
    path('my-admin/news/', views_admin.admin_news_list, name='admin_news_list'),
    path('my-admin/news/create/', views_admin.admin_news_create, name='admin_news_create'),
    path('my-admin/news/edit/<int:pk>/', views_admin.admin_news_edit, name='admin_news_edit'),
    path('my-admin/news/delete/<int:pk>/', views_admin.admin_news_delete, name='admin_news_delete'),
    path('my-admin/news/categories/', views_admin.admin_news_category, name='admin_news_category'),
    path('my-admin/news/toggle-pin/<int:pk>/', views_admin.admin_news_toggle_pin, name='admin_news_toggle_pin'),

    # Admin Sự kiện & Video YouTube
    path('my-admin/news/events/', views_admin.admin_event_list, name='admin_event_list'),
    path('my-admin/news/events/delete/<int:pk>/', views_admin.admin_event_delete, name='admin_event_delete'),
    path('my-admin/news/youtube/', views_admin.admin_youtube_list, name='admin_youtube_list'),
    path('my-admin/news/youtube/delete/<int:pk>/', views_admin.admin_youtube_delete, name='admin_youtube_delete'),

]
handler404 = 'apps.client.views.error_404'
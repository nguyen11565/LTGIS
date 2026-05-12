import os
import re

filepath = r'apps\client\views_admin.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update stock management for sales_staff
stock_mgmt_decorator = "@role_required(['super_admin', 'regional_manager', 'store_admin', 'warehouse_keeper'])\ndef admin_stock_management(request):"
stock_mgmt_new_decorator = "@role_required(['super_admin', 'regional_manager', 'store_admin', 'warehouse_keeper', 'sales_staff'])\ndef admin_stock_management(request):"
content = content.replace(stock_mgmt_decorator, stock_mgmt_new_decorator)

# Block POST for sales_staff
post_block = """    # --- 1. XỬ LÝ POST (NHẬP/XUẤT KHO) ---
    if request.method == "POST":"""
post_new = """    # --- 1. XỬ LÝ POST (NHẬP/XUẤT KHO) ---
    if request.method == "POST":
        if profile.role == 'sales_staff':
            messages.error(request, "Nhân viên bán hàng không có quyền thao tác kho.")
            return redirect("client:admin_stock_management")"""
content = content.replace(post_block, post_new)

# Remove the block that prevents sales_staff from viewing
sales_block = """    # Phân quyền hiển thị (Data Scoping)
    if profile.role == 'sales_staff':
        messages.error(request, "Nhân viên bán hàng không có quyền truy cập quản lý kho.")
        return redirect('client:admin_dashboard')
        
    if profile.role == 'super_admin':"""

sales_new = """    # Phân quyền hiển thị (Data Scoping)
    if profile.role == 'super_admin':"""
content = content.replace(sales_block, sales_new)

# Update else block scoping to include sales_staff
else_scoping = """    else:
        # store_admin, warehouse_keeper
        qs = StoreStock.objects.filter(store=profile.store).select_related('product', 'variation', 'store')"""
else_scoping_new = """    else:
        # store_admin, warehouse_keeper, sales_staff
        qs = StoreStock.objects.filter(store=profile.store).select_related('product', 'variation', 'store')"""
content = content.replace(else_scoping, else_scoping_new)


# 2. Update order_list, order_detail for warehouse_keeper
views_to_update = ['order_list', 'order_detail', 'print_invoice_view']
for view in views_to_update:
    pattern = r"@role_required\(\[(.*?)\]\)\ndef " + view + r"\(request"
    match = re.search(pattern, content)
    if match:
        roles_str = match.group(1)
        if "'warehouse_keeper'" not in roles_str:
            roles = [r.strip() for r in roles_str.split(',')]
            roles.append("'warehouse_keeper'")
            new_roles_str = ", ".join(roles)
            content = content.replace(f"@role_required([{roles_str}])\ndef {view}(request", f"@role_required([{new_roles_str}])\ndef {view}(request")


# For order_detail block POST from warehouse_keeper
order_post_block = """def order_detail(request, pk):
    order = get_object_or_404(Order, pk=pk)
    
    if request.method == 'POST':"""

order_post_new = """def order_detail(request, pk):
    order = get_object_or_404(Order, pk=pk)
    
    if request.method == 'POST':
        if request.user.profile.role == 'warehouse_keeper':
            messages.error(request, "Thủ kho không có quyền cập nhật trạng thái đơn hàng.")
            return redirect('client:admin_order_detail', pk=pk)"""

content = content.replace(order_post_block, order_post_new)

# Data scoping in order_list
order_list_scoping = """    elif profile.role in ['store_admin', 'sales_staff']:
        orders = Order.objects.filter(fulfillment_store=profile.store).order_by('-created_at')"""
order_list_scoping_new = """    elif profile.role in ['store_admin', 'sales_staff', 'warehouse_keeper']:
        orders = Order.objects.filter(fulfillment_store=profile.store).order_by('-created_at')"""
content = content.replace(order_list_scoping, order_list_scoping_new)

# Scoping for order_detail
order_detail_scoping = """    if profile.role in ['store_admin', 'sales_staff'] and order.fulfillment_store != profile.store:"""
order_detail_scoping_new = """    if profile.role in ['store_admin', 'sales_staff', 'warehouse_keeper'] and order.fulfillment_store != profile.store:"""
content = content.replace(order_detail_scoping, order_detail_scoping_new)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated views_admin.py for read-only roles")

import os
import re

filepath = r'apps\client\views_admin.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add 'sales_staff' to decorators for transfer_list, transfer_detail, stocktaking_list, stocktaking_detail
views_to_update = ['transfer_list', 'transfer_detail', 'stocktaking_list', 'stocktaking_detail']
for view in views_to_update:
    pattern = r"@role_required\(\[(.*?)\]\)\ndef " + view + r"\(request"
    match = re.search(pattern, content)
    if match:
        roles_str = match.group(1)
        if "'sales_staff'" not in roles_str:
            roles = [r.strip() for r in roles_str.split(',')]
            roles.append("'sales_staff'")
            new_roles_str = ", ".join(roles)
            content = content.replace(f"@role_required([{roles_str}])\ndef {view}(request", f"@role_required([{new_roles_str}])\ndef {view}(request")

# 2. Fix logic blocks inside transfer_list
transfer_list_sales_block = """    if profile.role == 'sales_staff':
        messages.error(request, "Nhân viên bán hàng không có quyền xem điều chuyển.")
        return redirect('client:admin_dashboard')
        
    if profile.role == 'super_admin':"""

transfer_list_new = """    if profile.role == 'super_admin':"""
content = content.replace(transfer_list_sales_block, transfer_list_new)

# 3. Fix logic blocks inside stocktaking_list
stocktaking_list_sales_block = """    if profile.role == 'sales_staff':
        messages.error(request, "Nhân viên bán hàng không có quyền truy cập phiếu kiểm kê.")
        return redirect('client:admin_dashboard')
        
    if profile.role == 'super_admin':"""

stocktaking_list_new = """    if profile.role == 'super_admin':"""
content = content.replace(stocktaking_list_sales_block, stocktaking_list_new)


with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("Updated views_admin.py for sales_staff viewing transfers and stocktakings")

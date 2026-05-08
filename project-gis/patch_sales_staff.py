import os
import re

def remove_sales_staff(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Xóa 'sales_staff' khỏi các view quản lý kho
    views_to_fix = [
        'def admin_stock_management',
        'def print_stock_transaction',
        'def store_detail',
        'def transfer_list',
        'def transfer_create',
        'def transfer_detail',
        'def transfer_action',
        'def stocktaking_list',
        'def stocktaking_create',
        'def stocktaking_detail',
        'def stocktaking_action',
    ]

    for view_func in views_to_fix:
        # Tìm decorator ngay phía trên view_func
        # pattern: @role_required([..., 'sales_staff', ...])\ndef view_func
        pattern = r"@role_required\(\[(.*?)\]\)\s+" + re.escape(view_func)
        match = re.search(pattern, content)
        if match:
            roles_str = match.group(1)
            # loại bỏ 'sales_staff'
            roles = [r.strip().strip("'").strip('"') for r in roles_str.split(',')]
            if 'sales_staff' in roles:
                roles.remove('sales_staff')
            
            new_roles_str = ", ".join(f"'{r}'" for r in roles)
            new_decorator = f"@role_required([{new_roles_str}])\n{view_func}"
            
            content = content[:match.start()] + new_decorator + content[match.end():]
            print(f"Fixed {view_func}")

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

remove_sales_staff(r'apps\client\views_admin.py')

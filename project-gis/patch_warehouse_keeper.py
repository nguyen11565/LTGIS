import os
import re

def remove_warehouse_keeper(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    views_to_fix = [
        'def order_list',
        'def order_detail',
        'def print_invoice_view',
        'def export_orders_excel'
    ]

    for view_func in views_to_fix:
        pattern = r"@role_required\(\[(.*?)\]\)\s+" + re.escape(view_func)
        match = re.search(pattern, content)
        if match:
            roles_str = match.group(1)
            roles = [r.strip().strip("'").strip('"') for r in roles_str.split(',')]
            if 'warehouse_keeper' in roles:
                roles.remove('warehouse_keeper')
            
            new_roles_str = ", ".join(f"'{r}'" for r in roles)
            new_decorator = f"@role_required([{new_roles_str}])\n{view_func}"
            
            content = content[:match.start()] + new_decorator + content[match.end():]
            print(f"Fixed {view_func}")
            
    # Also fix the order scoping in order_list:
    # regional_manager should see orders in their region
    target_scope = """    if profile.role == 'super_admin':
        orders = Order.objects.all().order_by('-created_at')
    else:
        if profile.store:"""
        
    replacement_scope = """    if profile.role == 'super_admin':
        orders = Order.objects.all().order_by('-created_at')
    elif profile.role == 'regional_manager':
        orders = Order.objects.filter(fulfillment_store__region=profile.region).order_by('-created_at')
    else:
        if profile.store:"""
        
    content = content.replace(target_scope, replacement_scope)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

remove_warehouse_keeper(r'apps\client\views_admin.py')

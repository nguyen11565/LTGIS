import re

with open('apps/client/views_admin.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace decorator ['super_admin', 'store_admin', 'staff']
content = content.replace(
    "@role_required(['super_admin', 'store_admin', 'staff'])",
    "@role_required(['super_admin', 'regional_manager', 'store_admin', 'warehouse_keeper', 'sales_staff'])"
)

# Replace decorator ['super_admin', 'store_admin']
content = content.replace(
    "@role_required(['super_admin', 'store_admin'])",
    "@role_required(['super_admin', 'regional_manager', 'store_admin'])"
)

with open('apps/client/views_admin.py', 'w', encoding='utf-8') as f:
    f.write(content)

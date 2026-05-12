import os

filepath = r'apps\client\views_admin.py'
with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# The error starts because of the dangling `else:` and duplicate blocks.
# I will replace lines 638 to 684 (0-indexed 637 to 683) with the unified logic.
new_logic = """
    if category_id: qs = qs.filter(product__category_id=category_id)
    if stock_status == 'in_stock': qs = qs.filter(quantity__gt=0)
    elif stock_status == 'out_of_stock': qs = qs.filter(quantity__lte=0)
    elif stock_status == 'low_stock': qs = qs.filter(quantity__gt=0, quantity__lt=10)

    for p in qs:
        stock_data.append({
            'product': p.product, 
            'variation': p.variation, 
            'stock': p.quantity, 
            'reserved': p.reserved_quantity,
            'available': p.available_quantity,
            'store_name': p.store.name if p.store else "Kho Tổng"
        })
        
    try:
        from apps.core.models import DefectiveProductStock
        defective_stock_data = DefectiveProductStock.objects.select_related('product', 'variation').all()
    except ImportError:
        defective_stock_data = []

"""

# Let's find exactly the range to replace to be safe.
# Find where the `        if category_id: qs = qs.filter(product__category_id=category_id)` starts.
start_idx = -1
for i, line in enumerate(lines):
    if "if category_id: qs = qs.filter(product__category_id=category_id)" in line and i > 600:
        start_idx = i
        break

if start_idx != -1:
    end_idx = -1
    for i in range(start_idx, len(lines)):
        if "return render(request, \"admin_custom/stock_management.html\"" in lines[i]:
            end_idx = i
            break
            
    if end_idx != -1:
        del lines[start_idx:end_idx]
        lines.insert(start_idx, new_logic)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        print("Fixed syntax error in views_admin.py")
    else:
        print("Could not find end index")
else:
    print("Could not find start index")

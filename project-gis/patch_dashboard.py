import os

def replace_in_file(filepath, replacements):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    for target, replacement in replacements:
        if target not in content:
            print(f"Target not found: {target[:50]}...")
        else:
            content = content.replace(target, replacement)
            print(f"Replaced successfully: {target[:50]}...")
            
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

replacements = [
    (
        """    if profile.role == 'super_admin':
        base_orders = Order.objects.all()
    else:
        if profile.store:
            base_orders = Order.objects.filter(fulfillment_store=profile.store)
        else:
            base_orders = Order.objects.none()""",
            
        """    if profile.role == 'super_admin':
        base_orders = Order.objects.all()
    elif profile.role == 'regional_manager':
        base_orders = Order.objects.filter(fulfillment_store__region=profile.region)
    else:
        if profile.store:
            base_orders = Order.objects.filter(fulfillment_store=profile.store)
        else:
            base_orders = Order.objects.none()"""
    ),
    (
        """    total_stores = Store.objects.count()""",
        """    if profile.role == 'super_admin':
        total_stores = Store.objects.count()
    elif profile.role == 'regional_manager':
        total_stores = Store.objects.filter(region=profile.region).count()
    else:
        total_stores = 1 if profile.store else 0"""
    )
]

replace_in_file(r'apps\client\views_admin.py', replacements)

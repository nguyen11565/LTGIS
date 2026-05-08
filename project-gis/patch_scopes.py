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
        # Hiển thị Kho Tổng thông qua StoreStock thay vì Product.stock
        main_warehouse = Store.objects.filter(is_warehouse=True).first()
        qs = StoreStock.objects.filter(store=main_warehouse).select_related('product', 'variation') if main_warehouse else StoreStock.objects.none()""",
        
        """    # Phân quyền hiển thị (Data Scoping)
    if profile.role == 'sales_staff':
        messages.error(request, "Nhân viên bán hàng không có quyền truy cập quản lý kho.")
        return redirect('client:admin_dashboard')
        
    if profile.role == 'super_admin':
        qs = StoreStock.objects.all().select_related('product', 'variation', 'store')
        transactions = StockTransaction.objects.all().select_related('product', 'variation', 'user', 'store_destination').order_by('-created_at')[:30]
    elif profile.role == 'regional_manager':
        qs = StoreStock.objects.filter(store__region=profile.region).select_related('product', 'variation', 'store')
        transactions = StockTransaction.objects.filter(store_destination__region=profile.region).select_related('product', 'variation', 'user', 'store_destination').order_by('-created_at')[:30]
    else:
        # store_admin, warehouse_keeper
        qs = StoreStock.objects.filter(store=profile.store).select_related('product', 'variation', 'store')
        transactions = StockTransaction.objects.filter(store_destination=profile.store).select_related('product', 'variation', 'user', 'store_destination').order_by('-created_at')[:30]
"""
    ),
    (
        """    if profile.role == 'super_admin':
        transfers = StockTransfer.objects.all()
    else:
        transfers = StockTransfer.objects.filter(Q(from_store=profile.store) | Q(to_store=profile.store))""",
        
        """    if profile.role == 'sales_staff':
        messages.error(request, "Nhân viên bán hàng không có quyền xem điều chuyển.")
        return redirect('client:admin_dashboard')
        
    if profile.role == 'super_admin':
        transfers = StockTransfer.objects.all()
    elif profile.role == 'regional_manager':
        from django.db.models import Q
        transfers = StockTransfer.objects.filter(Q(from_store__region=profile.region) | Q(to_store__region=profile.region))
    else:
        from django.db.models import Q
        transfers = StockTransfer.objects.filter(Q(from_store=profile.store) | Q(to_store=profile.store))"""
    ),
    (
        """    if profile.role == 'super_admin':
        stocktakings = Stocktaking.objects.all().select_related('store', 'created_by').order_by('-created_at')
    else:
        stocktakings = Stocktaking.objects.filter(store=profile.store).select_related('store', 'created_by').order_by('-created_at')""",
        
        """    if profile.role == 'sales_staff':
        messages.error(request, "Nhân viên bán hàng không có quyền xem kiểm kê.")
        return redirect('client:admin_dashboard')
        
    if profile.role == 'super_admin':
        stocktakings = Stocktaking.objects.all().select_related('store', 'created_by').order_by('-created_at')
    elif profile.role == 'regional_manager':
        stocktakings = Stocktaking.objects.filter(store__region=profile.region).select_related('store', 'created_by').order_by('-created_at')
    else:
        stocktakings = Stocktaking.objects.filter(store=profile.store).select_related('store', 'created_by').order_by('-created_at')"""
    )
]

replace_in_file(r'apps\client\views_admin.py', replacements)

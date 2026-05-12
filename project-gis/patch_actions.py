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
        """        if transfer.from_store != profile.store and profile.role != 'super_admin':
            messages.error(request, "Bạn không có quyền duyệt phiếu từ kho khác.")""",
            
        """        # Allow super_admin or regional_manager (if store in region) or store_admin (if store matches)
        has_perm = False
        if profile.role == 'super_admin': has_perm = True
        elif profile.role == 'regional_manager' and transfer.from_store.region == profile.region: has_perm = True
        elif profile.role in ['store_admin', 'warehouse_keeper'] and transfer.from_store == profile.store: has_perm = True
        
        if not has_perm:
            messages.error(request, "Bạn không có quyền duyệt phiếu xuất từ kho này.")"""
    ),
    (
        """        if transfer.to_store != profile.store and profile.role != 'super_admin':
            messages.error(request, "Bạn không có quyền nhận phiếu cho kho khác.")""",
            
        """        has_perm = False
        if profile.role == 'super_admin': has_perm = True
        elif profile.role == 'regional_manager' and transfer.to_store.region == profile.region: has_perm = True
        elif profile.role in ['store_admin', 'warehouse_keeper'] and transfer.to_store == profile.store: has_perm = True
        
        if not has_perm:
            messages.error(request, "Bạn không có quyền nhận phiếu cho kho này.")"""
    ),
    (
        """        if profile.role != 'super_admin' and stocktaking.store != profile.store:
            messages.error(request, "Bạn không có quyền duyệt phiếu kho này.")""",
            
        """        has_perm = False
        if profile.role == 'super_admin': has_perm = True
        elif profile.role == 'regional_manager' and stocktaking.store.region == profile.region: has_perm = True
        elif profile.role in ['store_admin', 'warehouse_keeper'] and stocktaking.store == profile.store: has_perm = True
        
        if not has_perm:
            messages.error(request, "Bạn không có quyền duyệt phiếu kiểm kê này.")"""
    )
]

replace_in_file(r'apps\client\views_admin.py', replacements)

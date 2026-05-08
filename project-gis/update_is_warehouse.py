import os

files_to_update = [
    r"apps\core\models.py",
    r"apps\core\management\commands\sync_stock.py",
    r"apps\client\views_admin.py",
    r"apps\client\views.py",
    r"apps\client\templates\admin_custom\store_list.html",
    r"apps\client\templates\admin_custom\store_detail.html"
]

for file_path in files_to_update:
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        content = content.replace("is_main_warehouse", "is_warehouse")
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Updated {file_path}")
    else:
        print(f"File not found: {file_path}")

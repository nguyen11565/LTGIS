import os

filepath = r'apps\client\views_admin.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Import Region
if 'Region' not in content[:1000]:
    content = content.replace('from apps.core.models import Store, Product', 'from apps.core.models import Region, Store, Product')

# Add region views after store views
region_views = """
# =========================================
# QUẢN LÝ KHU VỰC (REGIONS)
# =========================================
@role_required(['super_admin'])
def region_list(request):
    regions = Region.objects.all().order_by('name')
    return render(request, 'admin_custom/region_list.html', {'regions': regions})

@role_required(['super_admin'])
def region_add(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        
        if Region.objects.filter(name__iexact=name).exists():
            messages.error(request, f"Lỗi: Khu vực '{name}' đã tồn tại.")
            return render(request, 'admin_custom/region_form.html')
            
        Region.objects.create(name=name, description=description)
        messages.success(request, f"Đã thêm khu vực '{name}' thành công!")
        return redirect('client:admin_region_list')
        
    return render(request, 'admin_custom/region_form.html')

@role_required(['super_admin'])
def region_edit(request, pk):
    region = get_object_or_404(Region, pk=pk)
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        
        if Region.objects.filter(name__iexact=name).exclude(pk=pk).exists():
            messages.error(request, f"Lỗi: Khu vực '{name}' đã tồn tại.")
            return render(request, 'admin_custom/region_form.html', {'region': region})
            
        region.name = name
        region.description = description
        region.save()
        messages.success(request, f"Cập nhật khu vực '{name}' thành công!")
        return redirect('client:admin_region_list')
        
    return render(request, 'admin_custom/region_form.html', {'region': region})

@role_required(['super_admin'])
def region_delete(request, pk):
    region = get_object_or_404(Region, pk=pk)
    if request.method == 'POST':
        region.delete()
        messages.success(request, "Đã xóa khu vực thành công.")
    return redirect('client:admin_region_list')

"""

# find store_list
content = content.replace("def store_list(request):", region_views + "def store_list(request):")

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

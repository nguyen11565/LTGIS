import os

filepath = r'apps\client\views_admin.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace store_add
store_add_original = """def store_add(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        address = request.POST.get('address')
        description = request.POST.get('description', '')
        latitude = request.POST.get('latitude')
        phone = request.POST.get('phone')
        longitude = request.POST.get('longitude')
        image = request.FILES.get('image')

        if Store.objects.filter(name__iexact=name).exists():
            messages.error(request, f"Lỗi: Cửa hàng '{name}' đã tồn tại trong hệ thống.")
            return render(request, 'admin_custom/store_form.html')
        if Store.objects.filter(address__iexact=address).exists():
            messages.error(request, f"Lỗi: Địa chỉ '{address}' này đã được đăng ký cho chi nhánh khác.")
            return render(request, 'admin_custom/store_form.html')

        Store.objects.create(
            name=name, address=address, description=description,
            latitude=latitude, longitude=longitude, phone=phone, image=image
        )
        messages.success(request, f"Đã thêm cửa hàng '{name}' thành công!")
        return redirect('client:admin_store_list')

    return render(request, 'admin_custom/store_form.html')"""

store_add_new = """def store_add(request):
    regions = Region.objects.all()
    if request.method == 'POST':
        name = request.POST.get('name')
        address = request.POST.get('address')
        description = request.POST.get('description', '')
        latitude = request.POST.get('latitude')
        phone = request.POST.get('phone')
        longitude = request.POST.get('longitude')
        image = request.FILES.get('image')
        region_id = request.POST.get('region')
        is_warehouse = request.POST.get('is_warehouse') == 'on'

        if Store.objects.filter(name__iexact=name).exists():
            messages.error(request, f"Lỗi: Cửa hàng '{name}' đã tồn tại trong hệ thống.")
            return render(request, 'admin_custom/store_form.html', {'regions': regions})
        if Store.objects.filter(address__iexact=address).exists():
            messages.error(request, f"Lỗi: Địa chỉ '{address}' này đã được đăng ký cho chi nhánh khác.")
            return render(request, 'admin_custom/store_form.html', {'regions': regions})

        region = Region.objects.filter(id=region_id).first() if region_id else None

        Store.objects.create(
            name=name, address=address, description=description,
            latitude=latitude, longitude=longitude, phone=phone, image=image,
            region=region, is_warehouse=is_warehouse
        )
        messages.success(request, f"Đã thêm cửa hàng '{name}' thành công!")
        return redirect('client:admin_store_list')

    return render(request, 'admin_custom/store_form.html', {'regions': regions})"""

content = content.replace(store_add_original, store_add_new)

# Replace store_edit
store_edit_original = """def store_edit(request, pk):
    store = get_object_or_404(Store, pk=pk)
    if request.method == 'POST':
        name = request.POST.get('name')
        address = request.POST.get('address')
        description = request.POST.get('description', '')

        if Store.objects.filter(name__iexact=name).exclude(pk=pk).exists():
            messages.error(request, f"Lỗi: Cửa hàng '{name}' đã tồn tại trong hệ thống.")
            return render(request, 'admin_custom/store_form.html', {'store': store})
        if Store.objects.filter(address__iexact=address).exclude(pk=pk).exists():
            messages.error(request, f"Lỗi: Địa chỉ '{address}' này đã được đăng ký cho chi nhánh khác.")
            return render(request, 'admin_custom/store_form.html', {'store': store})

        store.name = name
        store.address = address
        store.description = description
        store.phone = request.POST.get('phone')
        store.latitude = request.POST.get('latitude')
        store.longitude = request.POST.get('longitude')
        
        new_image = request.FILES.get('image')
        if new_image:
            if store.image:
                import os
                from django.conf import settings
                old_path = os.path.join(settings.MEDIA_ROOT, str(store.image))
                if os.path.exists(old_path):
                    os.remove(old_path)
            store.image = new_image

        store.save()
        messages.success(request, f"Cập nhật cửa hàng '{name}' thành công!")
        return redirect('client:admin_store_list')

    return render(request, 'admin_custom/store_form.html', {'store': store})"""

store_edit_new = """def store_edit(request, pk):
    store = get_object_or_404(Store, pk=pk)
    regions = Region.objects.all()
    if request.method == 'POST':
        name = request.POST.get('name')
        address = request.POST.get('address')
        description = request.POST.get('description', '')
        region_id = request.POST.get('region')
        is_warehouse = request.POST.get('is_warehouse') == 'on'

        if Store.objects.filter(name__iexact=name).exclude(pk=pk).exists():
            messages.error(request, f"Lỗi: Cửa hàng '{name}' đã tồn tại trong hệ thống.")
            return render(request, 'admin_custom/store_form.html', {'store': store, 'regions': regions})
        if Store.objects.filter(address__iexact=address).exclude(pk=pk).exists():
            messages.error(request, f"Lỗi: Địa chỉ '{address}' này đã được đăng ký cho chi nhánh khác.")
            return render(request, 'admin_custom/store_form.html', {'store': store, 'regions': regions})

        store.name = name
        store.address = address
        store.description = description
        store.phone = request.POST.get('phone')
        store.latitude = request.POST.get('latitude')
        store.longitude = request.POST.get('longitude')
        store.region = Region.objects.filter(id=region_id).first() if region_id else None
        store.is_warehouse = is_warehouse
        
        new_image = request.FILES.get('image')
        if new_image:
            if store.image:
                import os
                from django.conf import settings
                old_path = os.path.join(settings.MEDIA_ROOT, str(store.image))
                if os.path.exists(old_path):
                    os.remove(old_path)
            store.image = new_image

        store.save()
        messages.success(request, f"Cập nhật cửa hàng '{name}' thành công!")
        return redirect('client:admin_store_list')

    return render(request, 'admin_custom/store_form.html', {'store': store, 'regions': regions})"""

content = content.replace(store_edit_original, store_edit_new)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)


from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.db.models import Sum
from django.db.models.functions import TruncDate
from django.utils.text import slugify  # Quan trọng: Dùng để tạo slug tự động
from datetime import datetime, timedelta
from django.db import transaction
from apps.core.models import Store, Product, Order, Category, OrderItem, StockTransaction, ProductImage
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse # Dùng cho chức năng xóa ảnh bằng AJAX

# =========================================
# 1. DASHBOARD & THỐNG KÊ
# =========================================

@staff_member_required(login_url='client:login')
def dashboard(request):
    total_stores = Store.objects.count()
    total_products = Product.objects.count()
    total_orders = Order.objects.count()

    today = datetime.now().date()
    seven_days_ago = today - timedelta(days=6)
    
    revenue_data = Order.objects.filter(
        status='completed', 
        created_at__date__gte=seven_days_ago
    ).annotate(date=TruncDate('created_at')) \
     .values('date') \
     .annotate(total=Sum('total_price')) \
     .order_by('date')

    labels = []
    data = []
    
    for i in range(7):
        date = seven_days_ago + timedelta(days=i)
        labels.append(date.strftime('%d/%m'))
        daily_total = next((item['total'] for item in revenue_data if item['date'] == date), 0)
        data.append(float(daily_total))

    context = {
        'total_stores': total_stores,
        'total_products': total_products,
        'total_orders': total_orders,
        'chart_labels': labels,
        'chart_data': data,
    }
    return render(request, 'admin_custom/dashboard.html', context)

# =========================================
# 2. QUẢN LÝ CỬA HÀNG (STORES)
# =========================================

@staff_member_required(login_url='client:login')
def store_list(request):
    stores = Store.objects.all().order_by('-id')
    return render(request, 'admin_custom/store_list.html', {'stores': stores})

@staff_member_required(login_url='client:login')
def store_add(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        address = request.POST.get('address')
        latitude = request.POST.get('latitude')
        phone = request.POST.get('phone')
        longitude = request.POST.get('longitude')
        image = request.FILES.get('image')

        Store.objects.create(
            name=name,
            address=address,
            latitude=latitude,
            longitude=longitude,
            image=image
        )
        messages.success(request, f"Đã thêm cửa hàng '{name}' thành công!")
        return redirect('client:admin_store_list')

    return render(request, 'admin_custom/store_form.html')

@staff_member_required(login_url='client:login')
def store_edit(request, pk):
    store = get_object_or_404(Store, pk=pk)
    if request.method == 'POST':
        store.name = request.POST.get('name')
        store.address = request.POST.get('address')
        store.phone = request.POST.get('phone')
        store.latitude = request.POST.get('latitude')
        store.longitude = request.POST.get('longitude')
        
        new_image = request.FILES.get('image')
        if new_image:
            store.image = new_image
            
        store.save()
        messages.success(request, f"Đã cập nhật chi tiết '{store.name}'!")
        return redirect('client:admin_store_list')

    return render(request, 'admin_custom/store_form.html', {'store': store})

@staff_member_required(login_url='client:login')
def store_delete(request, pk):
    store = get_object_or_404(Store, pk=pk)
    store_name = store.name
    store.delete()
    messages.warning(request, f"Đã xóa cửa hàng '{store_name}' khỏi hệ thống.")
    return redirect('client:admin_store_list')

# =========================================
# 3. QUẢN LÝ SẢN PHẨM & DANH MỤC
# =========================================

@staff_member_required(login_url='client:login')
def product_list(request):
    # 1. Lấy dữ liệu cơ bản
    categories = Category.objects.all().order_by('name')
    category_slug = request.GET.get('category')
    
    # 2. Lấy các tham số lọc mới từ thanh công cụ tìm kiếm
    search_query = request.GET.get('search')
    price_range = request.GET.get('price_range')
    
    # 3. Khởi tạo QuerySet sản phẩm
    products = Product.objects.all().order_by('-id')
    
    # --- BẮT ĐẦU LOGIC LỌC ---
    
    # Lọc theo danh mục (Giữ nguyên cũ)
    if category_slug:
        products = products.filter(category__slug=category_slug)
        
    # Lọc theo từ khóa tìm kiếm (Tên sản phẩm hoặc ID)
    if search_query:
        if search_query.isdigit():
            products = products.filter(id=search_query)
        else:
            products = products.filter(name__icontains=search_query)
            
    # Lọc theo khoảng giá (Mới thêm theo UI)
    if price_range:
        if price_range == '0-10':
            products = products.filter(price__lt=10000000)
        elif price_range == '10-20':
            products = products.filter(price__gte=10000000, price__lte=20000000)
        elif price_range == '20-30':
            products = products.filter(price__gte=20000000, price__lte=30000000)
        elif price_range == '30+':
            products = products.filter(price__gt=30000000)
            
    # --- KẾT THÚC LOGIC LỌC ---

    # 4. Chức năng thêm danh mục nhanh (Giữ nguyên cũ)
    if request.method == 'POST' and 'add_category' in request.POST:
        cat_name = request.POST.get('cat_name')
        if cat_name:
            new_slug = slugify(cat_name)
            # Kiểm tra tránh trùng lặp slug
            if not Category.objects.filter(slug=new_slug).exists():
                Category.objects.create(name=cat_name, slug=new_slug)
                messages.success(request, f"Đã thêm danh mục: {cat_name}")
                return redirect('client:admin_product_list')
            else:
                messages.error(request, "Danh mục này đã tồn tại.")

    context = {
        'categories': categories,
        'products': products,
        'selected_category': category_slug,
    }
    return render(request, 'admin_custom/product_management.html', context)
@staff_member_required(login_url='client:login')
def product_add(request):
    categories = Category.objects.all()
    if request.method == 'POST':
        name = request.POST.get('name')
        category_id = request.POST.get('category')
        price = request.POST.get('price')
        description = request.POST.get('description')
        content = request.POST.get('content') # LẤY DỮ LIỆU BÀI VIẾT CHI TIẾT
        image = request.FILES.get('image')
        
        category = get_object_or_404(Category, id=category_id)
        
        # 1. Tạo sản phẩm chính (Thêm trường content vào đây)
        product = Product.objects.create(
            name=name,
            category=category,
            price=price,
            description=description,
            content=content, # LƯU VÀO DATABASE
            image=image
        )

        # 2. Lưu nhiều ảnh phụ (Gallery)
        extra_images = request.FILES.getlist('more_images') 
        for img in extra_images:
            ProductImage.objects.create(product=product, image=img)

        messages.success(request, f"Đã thêm sản phẩm {name} thành công!")
        return redirect('client:admin_product_list')
        
    return render(request, 'admin_custom/product_form.html', {'categories': categories})

@staff_member_required(login_url='client:login')
def product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk)
    categories = Category.objects.all()
    
    if request.method == 'POST':
        product.name = request.POST.get('name')
        category_id = request.POST.get('category')
        product.category = get_object_or_404(Category, id=category_id)
        product.price = request.POST.get('price')
        product.description = request.POST.get('description')
        product.content = request.POST.get('content') # CẬP NHẬT DỮ LIỆU BÀI VIẾT CHI TIẾT
        
        new_image = request.FILES.get('image')
        if new_image:
            product.image = new_image
        
        product.save()

        # ==========================================
        # 1. CẬP NHẬT MỚI: Xử lý xóa ảnh trong Album
        # ==========================================
        images_to_delete = request.POST.getlist('delete_images')
        if images_to_delete:
            # Lọc ra các ảnh có ID nằm trong danh sách gửi lên và xóa chúng khỏi Database
            ProductImage.objects.filter(id__in=images_to_delete).delete()

        # ==========================================
        # 2. GIỮ NGUYÊN: Lưu thêm ảnh phụ mới nếu có
        # ==========================================
        extra_images = request.FILES.getlist('more_images')
        for img in extra_images:
            ProductImage.objects.create(product=product, image=img)

        messages.success(request, f"Cập nhật sản phẩm '{product.name}' thành công!")
        return redirect('client:admin_product_list')
        
    return render(request, 'admin_custom/product_form.html', {
        'product': product,
        'categories': categories
    })
@staff_member_required(login_url='client:login')
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    product.delete()
    messages.warning(request, "Đã xóa sản phẩm!")
    return redirect('client:admin_product_list')

# --- CHI TIẾT DANH MỤC (SỬA/XÓA) ---

@staff_member_required(login_url='client:login')
def category_edit(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if request.method == 'POST':
        new_name = request.POST.get('cat_name')
        if new_name:
            category.name = new_name
            category.slug = slugify(new_name)
            category.save()
            messages.success(request, f"Đã cập nhật danh mục thành: {new_name}")
    return redirect('client:admin_product_list')

@staff_member_required(login_url='client:login')
def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if category.products.exists():
        messages.error(request, f"Không thể xóa '{category.name}' vì vẫn còn sản phẩm thuộc danh mục này!")
    else:
        category.delete()
        messages.warning(request, f"Đã xóa danh mục '{category.name}' thành công.")
    return redirect('client:admin_product_list')

# =========================================
# 4. QUẢN LÝ ĐƠN HÀNG (ORDERS)
# =========================================

@staff_member_required(login_url='client:login')
def order_list(request):
    orders = Order.objects.all().order_by('-created_at') 
    return render(request, 'admin_custom/order_list.html', {'orders': orders})

@staff_member_required(login_url='client:login')
def order_list(request):
    # 1. Lấy danh sách tất cả đơn hàng (Sắp xếp mới nhất lên đầu)
    orders = Order.objects.all().order_by('-created_at')
    
    # 2. Lấy các tham số lọc từ URL (GET parameters)
    order_id = request.GET.get('order_id')
    status = request.GET.get('status')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')

    # 3. Áp dụng các bộ lọc nếu có
    # Lọc theo Mã Đơn
    if order_id and order_id.isdigit():
        orders = orders.filter(id=order_id)

    # Lọc theo Trạng thái
    if status:
        orders = orders.filter(status=status)

    # Lọc theo Ngày đặt (Từ ngày - Đến ngày)
    if start_date:
        try:
            # Lọc các đơn hàng có ngày tạo >= start_date
            orders = orders.filter(created_at__date__gte=datetime.strptime(start_date, '%Y-%m-%d').date())
        except ValueError:
            pass # Bỏ qua nếu định dạng ngày không hợp lệ

    if end_date:
        try:
            # Lọc các đơn hàng có ngày tạo <= end_date
            orders = orders.filter(created_at__date__lte=datetime.strptime(end_date, '%Y-%m-%d').date())
        except ValueError:
            pass

    # Lọc theo Tổng tiền
    if min_price and min_price.isdigit():
        orders = orders.filter(total_price__gte=int(min_price))
        
    if max_price and max_price.isdigit():
        orders = orders.filter(total_price__lte=int(max_price))

    # 4. Trả về template
    return render(request, 'admin_custom/order_list.html', {'orders': orders})


@staff_member_required(login_url='client:login')
def order_detail(request, pk):
    order = get_object_or_404(Order, pk=pk)
    order_items = order.items.all() 

    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status in dict(Order.STATUS_CHOICES):
            order.status = new_status
            order.save()
            messages.success(request, f"Đã cập nhật trạng thái đơn hàng #{order.id} thành công!")
            return redirect('client:admin_order_detail', pk=order.id)
    
    context = {
        'order': order,
        'order_items': order_items,
        'status_choices': Order.STATUS_CHOICES
    }
    return render(request, 'admin_custom/order_detail.html', context)

# =========================================
# 5. QUẢN LÝ KHO HÀNG (STOCK)
# =========================================

@staff_member_required(login_url='client:login')
def stock_management(request):
    # 1. Lấy dữ liệu cơ bản
    products = Product.objects.all().order_by("name")
    categories = Category.objects.all() # Lấy thêm categories để đổ vào form lọc
    transactions = StockTransaction.objects.all().select_related('product', 'user').order_by('-created_at')[:10]
    stores = Store.objects.all()

    # 2. LOGIC LỌC TÌM KIẾM (MỚI THÊM)
    category_id = request.GET.get('category')
    stock_status = request.GET.get('stock_status')

    # Lọc theo Danh mục
    if category_id:
        products = products.filter(category_id=category_id)

    # Lọc theo Trạng thái Tồn kho
    if stock_status == 'in_stock':
        products = products.filter(stock__gt=0)
    elif stock_status == 'out_of_stock':
        products = products.filter(stock__lte=0) # Dùng lte=0 để bắt cả trường hợp âm hoặc bằng 0
    elif stock_status == 'low_stock':
        products = products.filter(stock__gt=0, stock__lt=10)

    # 3. XỬ LÝ NHẬP/XUẤT KHO (GIỮ NGUYÊN)
    if request.method == "POST":
        product_id = request.POST.get("product_id")
        quantity_str = request.POST.get("quantity")
        t_type = request.POST.get("transaction_type")
        note = request.POST.get("note", "")
        import_price = request.POST.get("price") 
        store_id = request.POST.get("store_id")   

        if not product_id or not quantity_str:
            messages.error(request, "Dữ liệu không hợp lệ")
            return redirect("client:admin_stock_management")

        try:
            quantity = int(quantity_str)
            product = get_object_or_404(Product, id=product_id)

            if t_type == "in":
                product.stock = (product.stock or 0) + quantity
            elif t_type == "out":
                if (product.stock or 0) < quantity:
                    messages.error(request, f"Không đủ hàng trong kho (Hiện còn: {product.stock})")
                    return redirect("client:admin_stock_management")
                product.stock = product.stock - quantity
            
            product.save()

            StockTransaction.objects.create(
                product=product,
                quantity=quantity,
                transaction_type=t_type,
                note=note,
                user=request.user,
                price=float(import_price) if import_price and t_type == "in" else 0,
                store_destination_id=store_id if t_type == "out" and store_id else None
            )

            messages.success(request, f"Đã { 'nhập' if t_type == 'in' else 'xuất' } {quantity} {product.name} thành công")
            
        except Exception as e:
            messages.error(request, f"Có lỗi xảy ra: {str(e)}")

        return redirect("client:admin_stock_management")

    # 4. Gửi dữ liệu ra giao diện
    return render(request, "admin_custom/stock_management.html", {
            "products": products,
            "categories": categories, # Truyền thêm categories ra template
            "transactions": transactions,
            "stores": stores
        }
    )
@staff_member_required(login_url='client:login')
def print_stock_transaction(request, transaction_id):
    transaction = get_object_or_404(StockTransaction, id=transaction_id)
    return render(request, 'admin_custom/print_stock.html', {'t': transaction})

# =========================================
# 6. CHI TIẾT CỬA HÀNG & KHO TỔNG
# =========================================

@staff_member_required(login_url='client:login')
def store_detail(request, store_id):
    store = get_object_or_404(Store, id=store_id)
    
    if store.name == "Kho hàng PhoneStore":
        inventory = Product.objects.filter(stock__gt=0).values(
            'id', 'name', 'image', 'stock'
        ).annotate(total_quantity=Sum('stock'))
    else:
        inventory = StockTransaction.objects.filter(
            store_destination=store, 
            transaction_type='out'
        ).values(
            'product__id', 'product__name', 'product__image'
        ).annotate(total_quantity=Sum('quantity')).order_by('-total_quantity')

    return render(request, 'admin_custom/store_detail.html', {
        'store': store,
        'inventory': inventory,
        'is_main_warehouse': store.name == "Kho hàng PhoneStore"
    })

# =========================================
# 7. XÓA ẢNH TRONG GALLERY (AJAX/REDIRECT)
# =========================================

@staff_member_required(login_url='client:login')
def delete_product_image(request, img_id):
    image = get_object_or_404(ProductImage, id=img_id)
    product_id = image.product.id
    image.delete()
    messages.success(request, "Đã xóa ảnh khỏi bộ sưu tập.")
    return redirect('client:admin_product_edit', pk=product_id)
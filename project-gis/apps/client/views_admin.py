from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.db.models import Sum
from django.db.models.functions import TruncDate
from django.utils.text import slugify  # Quan trọng: Dùng để tạo slug tự động
from datetime import datetime, timedelta
from django.contrib import messages
from django.db import transaction
from apps.core.models import Product, StockTransaction


# Import models
from apps.core.models import Store, Product, Order, Category, OrderItem

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
    categories = Category.objects.all().order_by('name')
    
    # Lấy slug danh mục từ tham số GET trên URL (ví dụ: ?category=iphone)
    category_slug = request.GET.get('category')
    
    if category_slug:
        # Lọc sản phẩm thuộc danh mục có slug tương ứng
        # Lưu ý: Dùng 'category__slug' vì Product liên kết với Category
        products = Product.objects.filter(category__slug=category_slug).order_by('-id')
    else:
        # Nếu không có tham số, hiển thị tất cả sản phẩm như cũ
        products = Product.objects.all().order_by('-id')

    # --- Phần xử lý POST (thêm danh mục) giữ nguyên như cũ ---
    if request.method == 'POST' and 'add_category' in request.POST:
        cat_name = request.POST.get('cat_name')
        if cat_name:
            new_slug = slugify(cat_name)
            if not Category.objects.filter(slug=new_slug).exists():
                Category.objects.create(name=cat_name, slug=new_slug)
                messages.success(request, f"Đã thêm danh mục: {cat_name}")
                return redirect('client:admin_product_list')

    context = {
        'categories': categories,
        'products': products,
        'selected_category': category_slug, # Gửi slug đang chọn về template
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
        image = request.FILES.get('image')
        
        category = get_object_or_404(Category, id=category_id)
        
        Product.objects.create(
            name=name,
            category=category,
            price=price,
            description=description,
            image=image
        )
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
        
        new_image = request.FILES.get('image')
        if new_image:
            product.image = new_image
            
        product.save()
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
            category.slug = slugify(new_name) # Cập nhật slug theo tên mới
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

#nhập xuất kho
def stock_management(request):
    # 1. Lấy dữ liệu hiển thị (Dùng đúng tên model mới StockTransaction)
    products = Product.objects.all().order_by("name")
    transactions = StockTransaction.objects.all().order_by('-created_at')[:10]

    if request.method == "POST":
        product_id = request.POST.get("product_id")
        quantity_str = request.POST.get("quantity")
        t_type = request.POST.get("transaction_type")
        note = request.POST.get("note", "") # Lấy thêm ghi chú từ form

        if not product_id or not quantity_str:
            messages.error(request, "Dữ liệu không hợp lệ")
            return redirect("client:admin_stock_management")

        quantity = int(quantity_str)
        product = get_object_or_404(Product, id=product_id)

        # 2. Cập nhật tồn kho của Sản phẩm
        if t_type == "in":
            product.stock = product.stock + quantity
        elif t_type == "out":
            if product.stock < quantity:
                messages.error(request, f"Không đủ hàng (Hiện còn: {product.stock})")
                return redirect("client:admin_stock_management")
            product.stock = product.stock - quantity
        
        product.save()

        # 3. QUAN TRỌNG: Tạo bản ghi lịch sử giao dịch (Chỗ này bạn đang thiếu)
        StockTransaction.objects.create(
            product=product,
            quantity=quantity,
            transaction_type=t_type,
            note=note,
            user=request.user # Lưu người thực hiện
        )

        messages.success(request, f"Đã { 'nhập' if t_type == 'in' else 'xuất' } {quantity} {product.name} thành công")
        return redirect("client:admin_stock_management")

    return render(
        request,
        "admin_custom/stock_management.html",
        {
            "products": products,
            "transactions": transactions
        }
    )
# In hóa đơn nhập xuất kho
@staff_member_required
def print_stock_transaction(request, transaction_id):
    transaction = get_object_or_404(StockTransaction, id=transaction_id)
    return render(request, 'admin_custom/print_stock.html', {'t': transaction})
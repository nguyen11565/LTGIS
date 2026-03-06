from django.shortcuts import render, redirect, get_object_or_404
from apps.core.models import Store, Product, Order
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from apps.core.models import Product, Category
from apps.core.models import Order
from django.db.models import Sum
from django.db.models.functions import TruncDate
from datetime import datetime, timedelta
from apps.core.models import Category

@staff_member_required(login_url='client:login')
@staff_member_required(login_url='client:login')
def dashboard(request):
    # Các thống kê tổng quát đã có
    total_stores = Store.objects.count()
    total_products = Product.objects.count()
    total_orders = Order.objects.count()

    # Tính doanh thu 7 ngày gần đây
    today = datetime.now().date()
    seven_days_ago = today - timedelta(days=6)
    
    # Truy vấn lấy tổng tiền theo từng ngày
    revenue_data = Order.objects.filter(
        status='completed', 
        created_at__date__gte=seven_days_ago
    ).annotate(date=TruncDate('created_at')) \
     .values('date') \
     .annotate(total=Sum('total_price')) \
     .order_by('date')

    # Chuẩn bị dữ liệu cho Chart.js
    labels = []
    data = []
    
    # Tạo danh sách 7 ngày đầy đủ (kể cả những ngày doanh thu = 0)
    for i in range(7):
        date = seven_days_ago + timedelta(days=i)
        labels.append(date.strftime('%d/%m'))
        
        # Tìm doanh thu của ngày đó trong kết quả truy vấn
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

@staff_member_required(login_url='client:login')
def store_list(request):
    stores = Store.objects.all().order_by('-id') # Hiện cửa hàng mới nhất lên đầu
    return render(request, 'admin_custom/store_list.html', {'stores': stores})

@staff_member_required(login_url='client:login')
def store_add(request):
    if request.method == 'POST':
        # Lấy dữ liệu từ các thẻ input name="..." trong form
        name = request.POST.get('name')
        address = request.POST.get('address')
        latitude = request.POST.get('latitude')
        longitude = request.POST.get('longitude')
        image = request.FILES.get('image') # Lấy file ảnh

        # Lưu vào Database
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
        # Cập nhật thông tin mới
        store.name = request.POST.get('name')
        store.address = request.POST.get('address')
        store.latitude = request.POST.get('latitude')
        store.longitude = request.POST.get('longitude')
        
        # Kiểm tra nếu người dùng có upload ảnh mới thì mới cập nhật ảnh
        new_image = request.FILES.get('image')
        if new_image:
            store.image = new_image
            
        store.save() # Lưu thay đổi
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

# QUẢN LÝ SẢN PHẨM
@staff_member_required(login_url='client:login')
def product_list(request):
    # Lấy dữ liệu cho 2 phần trên cùng 1 trang
    categories = Category.objects.all().order_by('name')
    products = Product.objects.all().order_by('-id')

    # Xử lý nếu người dùng nhấn thêm danh mục nhanh bằng POST
    if request.method == 'POST' and 'add_category' in request.POST:
        cat_name = request.POST.get('cat_name')
        if cat_name:
            Category.objects.create(name=cat_name)
            messages.success(request, f"Đã thêm danh mục: {cat_name}")
            return redirect('client:admin_product_list')

    context = {
        'categories': categories,
        'products': products,
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
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    product.delete()
    messages.warning(request, "Đã xóa sản phẩm!")
    return redirect('client:admin_product_list')

@staff_member_required(login_url='client:login')
def product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk)
    categories = Category.objects.all()
    
    if request.method == 'POST':
        # Lấy dữ liệu mới từ form
        product.name = request.POST.get('name')
        category_id = request.POST.get('category')
        product.category = get_object_or_404(Category, id=category_id)
        product.price = request.POST.get('price')
        product.description = request.POST.get('description')
        
        # Kiểm tra nếu có upload ảnh mới
        new_image = request.FILES.get('image')
        if new_image:
            product.image = new_image
            
        product.save() # Lưu thay đổi vào Database
        messages.success(request, f"Cập nhật sản phẩm '{product.name}' thành công!")
        return redirect('client:admin_product_list')
        
    return render(request, 'admin_custom/product_form.html', {
        'product': product,
        'categories': categories
    })

# QUẢN LÝ ĐƠN HÀNG
@staff_member_required(login_url='client:login')
def order_list(request):
    # Lấy tất cả đơn hàng, sắp xếp mới nhất lên đầu
    orders = Order.objects.all().order_by('-created_at') 
    return render(request, 'admin_custom/order_list.html', {'orders': orders})

@staff_member_required(login_url='client:login')
@staff_member_required(login_url='client:login')
def order_detail(request, pk):
    order = get_object_or_404(Order, pk=pk)
    order_items = order.items.all() 

    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status in dict(Order.STATUS_CHOICES): # Đảm bảo trạng thái hợp lệ
            order.status = new_status
            order.save()
            messages.success(request, f"Đã cập nhật trạng thái đơn hàng #{order.id} thành công!")
            return redirect('client:admin_order_detail', pk=order.id)
    
    context = {
        'order': order,
        'order_items': order_items,
        'status_choices': Order.STATUS_CHOICES # Truyền danh sách trạng thái để render dropdown
    }
    return render(request, 'admin_custom/order_detail.html', context)

#xoa sua category
@staff_member_required(login_url='client:login')
def category_edit(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if request.method == 'POST':
        new_name = request.POST.get('cat_name')
        if new_name:
            category.name = new_name
            category.save()
            messages.success(request, f"Đã cập nhật danh mục thành: {new_name}")
    return redirect('client:admin_product_list')

@staff_member_required(login_url='client:login')
def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk)
    # Kiểm tra xem danh mục có sản phẩm không trước khi xóa
    if category.product_set.exists():
        messages.error(request, f"Không thể xóa '{category.name}' vì vẫn còn sản phẩm thuộc danh mục này!")
    else:
        category.delete()
        messages.warning(request, "Đã xóa danh mục thành công.")
    return redirect('client:admin_product_list')
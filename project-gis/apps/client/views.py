import json
from django.core.serializers.json import DjangoJSONEncoder
from django.shortcuts import render, redirect, get_object_or_404
from apps.core.models import Product, Category, Store, Order, OrderItem
from .cart import Cart 
from .utils import haversine_distance 
from django.utils import timezone 
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.db.models import Sum

# =========================================
# 1. TRANG CHỦ & DANH MỤC
# =========================================

def home(request):
    # 1. Lấy ID danh mục từ URL (ví dụ: ?category=1)
    category_id = request.GET.get('category')
    categories = Category.objects.all().order_by('name')
    
    if category_id:
        # Lọc sản phẩm theo danh mục nếu có yêu cầu
        products = Product.objects.filter(category_id=category_id).order_by('-id')
        current_category = get_object_or_404(Category, id=category_id)
    else:
        # Mặc định lấy tất cả sản phẩm mới nhất
        products = Product.objects.all().order_by('-id')
        current_category = None
    
    # Logic lấy Sản phẩm mới/nổi bật
    products = Product.objects.all().order_by('-id')
    
    # LOGIC MỚI: Lấy Top 5 sản phẩm bán chạy nhất
    # Ta tính tổng quantity trong OrderItem cho mỗi sản phẩm của đơn hàng đã 'completed'
    best_selling_products = Product.objects.filter(
        orderitem__order__status='completed'
    ).annotate(
        total_sold=Sum('orderitem__quantity')
    ).order_by('-total_sold')[:5]

    context = {
        'products': products,
        'categories': categories,
        'best_selling_products': best_selling_products, # Chuyền thêm dữ liệu này
        'current_category': None,
    }
    return render(request, 'client/home.html', context)

# =========================================
# 2. TÌM KIẾM SẢN PHẨM
# =========================================

def search_view(request):
    query = request.GET.get('q')
    results = []
    if query:
        # Tìm kiếm theo tên hoặc mô tả
        results = Product.objects.filter(
            Q(name__icontains=query) | Q(description__icontains=query)
        ).distinct().order_by('-id')
    
    context = {
        'query': query,
        'results': results,
    }
    return render(request, 'client/search_results.html', context)

# =========================================
# 3. GIỎ HÀNG (CART)
# =========================================

def cart_detail(request):
    cart = Cart(request)
    return render(request, 'client/cart.html', {'cart': cart})

def cart_add(request, product_id):
    cart = Cart(request)
    product = get_object_or_404(Product, id=product_id)
    cart.add(product=product, quantity=1)
    return redirect('client:cart')

def cart_remove(request, product_id):
    cart = Cart(request)
    product = get_object_or_404(Product, id=product_id)
    cart.remove(product)
    return redirect('client:cart')

# =========================================
# 4. CHI TIẾT SẢN PHẨM
# =========================================

def product_detail(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    # Gợi ý sản phẩm cùng danh mục
    related_products = Product.objects.filter(category=product.category).exclude(id=product.id)[:4]
    
    return render(request, 'client/product_detail.html', {
        'product': product,
        'related_products': related_products
    })

# =========================================
# 5. CỬA HÀNG (STORE LOCATOR)
# =========================================

def store_locator(request):
    user_lat = float(request.GET.get('lat', 10.7725))
    user_lon = float(request.GET.get('lon', 106.6980))
    now = timezone.localtime().time()
    stores = Store.objects.all()
    store_list = []
    districts = set()

    for store in stores:
        dist = haversine_distance(user_lat, user_lon, store.latitude, store.longitude)
        if hasattr(store, 'district') and store.district:
            districts.add(store.district)
        
        is_open = True
        if hasattr(store, 'opening_time') and hasattr(store, 'closing_time'):
            is_open = store.opening_time <= now <= store.closing_time
        
        image_url = store.image.url if hasattr(store, 'image') and store.image else "https://via.placeholder.com/400x200?text=Phone+Store"

        store_list.append({
            'name': store.name,
            'lat': store.latitude,
            'lon': store.longitude,
            'address': store.address,
            'phone': store.phone,
            'image_url': image_url,
            'district': getattr(store, 'district', ''),
            'distance': round(dist, 2),
            'is_open': is_open,
            'open_hours': f"{store.opening_time.strftime('%H:%M')} - {store.closing_time.strftime('%H:%M')}" if hasattr(store, 'opening_time') else "08:00 - 21:00"
        })

    store_list.sort(key=lambda x: x['distance'])
    stores_json = json.dumps(store_list, cls=DjangoJSONEncoder)

    return render(request, 'client/store_locator.html', {
        'stores_json': stores_json,
        'user_lat': user_lat,
        'user_lon': user_lon,
        'districts': sorted(list(districts))
    })

# =========================================
# 6. THANH TOÁN (CHECKOUT)
# =========================================

def checkout(request):
    cart = Cart(request)
    if cart.get_total_price() == 0:
        return redirect('client:home')

    if request.method == 'POST':
        name = request.POST.get('fullname')
        phone = request.POST.get('phone')
        address = request.POST.get('address')
        
        order = Order.objects.create(
            user=request.user if request.user.is_authenticated else None,
            full_name=name,
            phone=phone,
            address=address,
            total_price=cart.get_total_price()
        )
        
        for item in cart:
            OrderItem.objects.create(
                order=order,
                product=item['product'],
                price=item['price'],
                quantity=item['quantity']
            )
            
        cart.clear()
        messages.success(request, "Đặt hàng thành công! Bạn có thể theo dõi đơn hàng tại đây.")
        return render(request, 'client/success.html', {'order': order})
        
    return render(request, 'client/checkout.html', {'cart': cart})

# =========================================
# 7. TÀI KHOẢN & ĐƠN HÀNG
# =========================================

def register_view(request):
    if request.method == 'POST':
        u = request.POST.get('username')
        e = request.POST.get('email')
        p = request.POST.get('password')
        
        if User.objects.filter(username=u).exists():
            messages.error(request, "Tên đăng nhập đã tồn tại")
        else:
            user = User.objects.create_user(username=u, email=e, password=p)
            login(request, user)
            messages.success(request, "Đăng ký thành công!")
            return redirect('client:home')
    return render(request, 'client/register.html')

def login_view(request):
    if request.method == 'POST':
        u = request.POST.get('username')
        p = request.POST.get('password')
        user = authenticate(username=u, password=p)
        if user:
            login(request, user)
            return redirect('client:home')
        else:
            messages.error(request, "Sai tài khoản hoặc mật khẩu")
    return render(request, 'client/login.html')

def logout_view(request):
    logout(request)
    return redirect('client:home')

@login_required(login_url='client:login')
def my_orders(request):
    orders = Order.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'client/my_orders.html', {'orders': orders})
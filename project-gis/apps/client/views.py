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
from apps.core.models import Order, OrderItem

# =========================================
# 1. TRANG CHỦ & DANH MỤC
# =========================================

def home(request):
    # 1. Lấy dữ liệu cơ bản từ request
    category_id = request.GET.get('category')
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    price_range = request.GET.get('price_range')
    
    categories = Category.objects.all().order_by('name')
    
    # 2. Logic lọc sản phẩm theo danh mục (Đã sửa lỗi ghi đè)
    if category_id:
        # Lọc sản phẩm theo danh mục
        products = Product.objects.filter(category_id=category_id).order_by('-id')
        current_category = get_object_or_404(Category, id=category_id)
    else:
        # Mặc định lấy tất cả sản phẩm mới nhất
        products = Product.objects.all().order_by('-id')
        current_category = None
    
    # 3. THÊM MỚI: Logic lọc theo mức giá (price_range hoặc min/max)
    # Chú ý: Chúng ta tiếp tục dùng biến 'products' ở trên để lọc tiếp, 
    # giúp khách hàng có thể vừa chọn Hãng vừa chọn Giá cùng lúc.
    if price_range:
        # Nếu người dùng chọn các mức giá có sẵn (Radio button)
        if price_range == '1-3':
            products = products.filter(price__gte=1000000, price__lte=3000000)
        elif price_range == '3-5':
            products = products.filter(price__gte=3000000, price__lte=5000000)
        elif price_range == '5-10':
            products = products.filter(price__gte=5000000, price__lte=10000000)
        elif price_range == '10-15':
            products = products.filter(price__gte=10000000, price__lte=15000000)
        elif price_range == '15-20':
            products = products.filter(price__gte=15000000, price__lte=20000000)
        elif price_range == '20-25':
            products = products.filter(price__gte=20000000, price__lte=25000000)
        elif price_range == '25-30':
            products = products.filter(price__gte=25000000, price__lte=30000000)
        elif price_range == '30-50':
            products = products.filter(price__gte=30000000, price__lte=50000000)
        elif price_range == '50-85':
            products = products.filter(price__gte=50000000, price__lte=85000000)
        elif price_range == '85+':
            products = products.filter(price__gte=85000000)
    else:
        # Nếu không chọn khoảng giá sẵn, kiểm tra xem có kéo thanh trượt không
        if min_price and min_price.isdigit():
            products = products.filter(price__gte=int(min_price))
        if max_price and max_price.isdigit():
            products = products.filter(price__lte=int(max_price))

    # 4. LOGIC Lấy Top 5 sản phẩm bán chạy nhất
    best_selling_products = Product.objects.filter(
        orderitem__order__status='completed'
    ).annotate(
        total_sold=Sum('orderitem__quantity')
    ).order_by('-total_sold')[:5]

    # 5. Truyền dữ liệu ra template
    context = {
        'products': products,
        'categories': categories,
        'best_selling_products': best_selling_products,
        'current_category': current_category,
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
    # Lấy danh sách ảnh phụ của sản phẩm này
    product_images = product.images.all() 
    
    # Gợi ý sản phẩm cùng danh mục
    related_products = Product.objects.filter(category=product.category).exclude(id=product.id)[:4]
    
    return render(request, 'client/product_detail.html', {
        'product': product,
        'product_images': product_images, # Truyền biến này xuống template
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
@login_required(login_url='client:login')
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
    # Lấy tham số 'next' từ URL (nếu có)
    next_url = request.GET.get('next')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            
            # Nếu là Admin
            if user.is_staff or user.is_superuser:
                messages.success(request, f"Chào Admin {user.username}!")
                return redirect('client:admin_dashboard') 
            
            # Nếu là Khách hàng bình thường
            else:
                # Nếu có đường dẫn 'next' (ví dụ đang từ giỏ hàng bị bắt đăng nhập) -> Trả về trang đó
                if next_url:
                    return redirect(next_url)
                
                # Nếu đăng nhập bình thường -> Về trang chủ
                messages.success(request, "Đăng nhập thành công!")
                return redirect('client:home') 
            
        else:
            messages.error(request, "Tên đăng nhập hoặc mật khẩu không chính xác.")
            
    return render(request, 'client/login.html')

def logout_view(request):
    logout(request)
    return redirect('client:home')

@login_required(login_url='client:login')
def my_orders(request):
    orders = Order.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'client/my_orders.html', {'orders': orders})

def order_detail(request, order_id):
    # Lấy đơn hàng, đảm bảo đơn hàng đó thuộc về người dùng đang đăng nhập
    order = get_object_or_404(Order, id=order_id, user=request.user)
    # Lấy danh sách sản phẩm trong đơn hàng
    items = order.items.all() 
    
    return render(request, 'client/order_detail.html', {
        'order': order,
        'items': items
    })

def cancel_order(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    
    # Chỉ cho phép hủy nếu đơn hàng đang chờ xác nhận
    if order.status == 'pending':
        order.status = 'cancelled'
        order.save()
        messages.success(request, f"Đã hủy đơn hàng #{order.id} thành công.")
    else:
        messages.error(request, "Không thể hủy đơn hàng này do đã được xử lý hoặc đã giao.")
        
    return redirect('client:order_detail', order_id=order.id)

def error_404(request, exception):
    return render(request, '404.html', status=404)
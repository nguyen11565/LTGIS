import json # Dùng để xử lý dữ liệu bản đồ
from django.core.serializers.json import DjangoJSONEncoder # Dùng để gửi dữ liệu sang JS
from django.shortcuts import render, redirect, get_object_or_404
from apps.core.models import Product, Category, Store # <-- Nhớ thêm Store vào đây
from apps.core.models import Product, Category, Store, Order, OrderItem
# Import các file hỗ trợ bên cạnh
from .cart import Cart 
from .utils import haversine_distance # <-- Import hàm tính toán khoảng cách
from django.utils import timezone # Thêm để xử lý giờ mở cửa

# =========================================
# 1. CÁC VIEW CŨ (TRANG CHỦ & GIỎ HÀNG)
# =========================================

def home(request):
    # Lấy sản phẩm mới nhất
    products = Product.objects.all().order_by('-id')
    # Lấy danh mục (nếu cần hiển thị menu)
    categories = Category.objects.all()
    
    context = {
        'products': products,
        'categories': categories,
    }
    return render(request, 'client/home.html', context)

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
# 2. VIEW MỚI: TÌM CỬA HÀNG (STORE LOCATOR)
# =========================================

def store_locator(request):
    # 1. Lấy tọa độ từ trình duyệt gửi lên
    user_lat = float(request.GET.get('lat', 10.7725))
    user_lon = float(request.GET.get('lon', 106.6980))

    # Lấy giờ hiện tại của hệ thống (Asia/Ho_Chi_Minh)
    now = timezone.localtime().time()

    stores = Store.objects.all()
    store_list = []
    districts = set() # Dùng tập hợp để lấy danh sách Quận duy nhất

    # 2. Tính toán dữ liệu cho từng cửa hàng
    for store in stores:
        dist = haversine_distance(user_lat, user_lon, store.latitude, store.longitude)
        
        # Thêm quận vào danh sách lọc (nếu có trường district trong Model)
        if hasattr(store, 'district') and store.district:
            districts.add(store.district)
        
        # Kiểm tra trạng thái đóng/mở cửa
        is_open = True
        if hasattr(store, 'opening_time') and hasattr(store, 'closing_time'):
            is_open = store.opening_time <= now <= store.closing_time
        
        # Kiểm tra nếu cửa hàng có trường image và đã được upload ảnh
        if hasattr(store, 'image') and store.image:
            image_url = store.image.url
        else:
            # Đường dẫn ảnh mặc định nếu không có ảnh (có thể dùng ảnh trong static hoặc link online)
            image_url = "https://via.placeholder.com/400x200?text=Phone+Store"

        store_list.append({
            'name': store.name,
            'lat': store.latitude,
            'lon': store.longitude,
            'address': store.address,
            'phone': store.phone,
            'image_url': image_url,
            'district': getattr(store, 'district', ''), # Lấy quận nếu có
            'distance': round(dist, 2),
            'is_open': is_open,
            'open_hours': f"{store.opening_time.strftime('%H:%M')} - {store.closing_time.strftime('%H:%M')}" if hasattr(store, 'opening_time') else "08:00 - 21:00"
        })

    # 3. Sắp xếp theo khoảng cách gần nhất
    store_list.sort(key=lambda x: x['distance'])

    # 4. Chuyển JSON
    stores_json = json.dumps(store_list, cls=DjangoJSONEncoder)

    return render(request, 'client/store_locator.html', {
        'stores_json': stores_json,
        'user_lat': user_lat,
        'user_lon': user_lon,
        'districts': sorted(list(districts)) # Gửi danh sách quận đã sắp xếp sang HTML
    })
    # --- VIEW CHI TIẾT SẢN PHẨM ---
def product_detail(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    # Gợi ý sản phẩm cùng danh mục
    related_products = Product.objects.filter(category=product.category).exclude(id=product.id)[:4]
    
    return render(request, 'client/product_detail.html', {
        'product': product,
        'related_products': related_products
    })

# --- VIEW THANH TOÁN (CHECKOUT) ---
def checkout(request):
    cart = Cart(request)
    if cart.get_total_price() == 0:
        return redirect('client:home')

    if request.method == 'POST':
        # 1. Lấy thông tin từ form
        name = request.POST.get('fullname')
        phone = request.POST.get('phone')
        address = request.POST.get('address')
        
        # 2. Tạo đơn hàng
        order = Order.objects.create(
            full_name=name,
            phone=phone,
            address=address,
            total_price=cart.get_total_price()
        )
        
        # 3. Lưu chi tiết từng món hàng
        for item in cart:
            OrderItem.objects.create(
                order=order,
                product=item['product'],
                price=item['price'],
                quantity=item['quantity']
            )
            
        # 4. Xóa giỏ hàng và thông báo thành công
        cart.clear()
        return render(request, 'client/success.html', {'order': order})
        
    return render(request, 'client/checkout.html', {'cart': cart})
import json # Dùng để xử lý dữ liệu bản đồ
from django.core.serializers.json import DjangoJSONEncoder # Dùng để gửi dữ liệu sang JS
from django.shortcuts import render, redirect, get_object_or_404
from apps.core.models import Product, Category, Store # <-- Nhớ thêm Store vào đây
from apps.core.models import Product, Category, Store, Order, OrderItem
# Import các file hỗ trợ bên cạnh
from .cart import Cart 
from .utils import haversine_distance # <-- Import hàm tính toán khoảng cách

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
    # 1. Giả lập vị trí người dùng (Ví dụ: Đang ở Chợ Bến Thành, Q1, TP.HCM)
    # Sau này bạn có thể dùng JavaScript để lấy vị trí thật của trình duyệt gửi lên
    user_lat = 10.8627
    user_lon = 106.61901

    stores = Store.objects.all()
    store_list = []

    # 2. Tính khoảng cách từ người dùng đến từng cửa hàng
    for store in stores:
        # Gọi hàm tính toán từ file utils.py
        dist = haversine_distance(user_lat, user_lon, store.latitude, store.longitude)
        
        store_list.append({
            'name': store.name,
            'lat': store.latitude,
            'lon': store.longitude,
            'address': store.address,
            'distance': round(dist, 2) # Làm tròn 2 số thập phân
        })

    # 3. Sắp xếp danh sách: Cửa hàng gần nhất lên đầu
    store_list.sort(key=lambda x: x['distance'])

    # 4. Chuyển dữ liệu thành JSON để bản đồ Leaflet đọc được
    stores_json = json.dumps(store_list, cls=DjangoJSONEncoder)

    return render(request, 'client/store_locator.html', {
        'stores_json': stores_json,
        'user_lat': user_lat,
        'user_lon': user_lon
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
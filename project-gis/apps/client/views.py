import json
from django.core.serializers.json import DjangoJSONEncoder
from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from apps.core.models import Product, Category, Store, Order, OrderItem
from .cart import Cart 
from .utils import haversine_distance 
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.db.models import Sum
from apps.core.models import Order, OrderItem, Coupon, UserProfile, ShippingAddress, Store, Product, StoreStock, Review, Notification, ReturnRequest, ReturnItem
from decimal import Decimal
from django.urls import reverse
from django.http import HttpResponse, JsonResponse
from openpyxl import Workbook, load_workbook
# Email imports
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
# =========================================
# 1. TRANG CHỦ & DANH MỤC
# - home(): Trang chủ (lọc danh mục, giá, tồn kho, top bán chạy, flash sale, tin tức)
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
    
    stock_status = request.GET.get('stock_status')
    if stock_status:
        if stock_status == 'in_stock':
            products = products.filter(stock__gt=0)
        elif stock_status == 'out_of_stock':
            products = products.filter(stock__lte=0)

    # 4. LOGIC Lấy Top 5 sản phẩm bán chạy nhất
    best_selling_products = Product.objects.filter(
        orderitem__order__status='completed'
    ).annotate(
        total_sold=Sum('orderitem__quantity')
    ).order_by('-total_sold')[:5]

    # 5. Phân trang sản phẩm - 12 sản phẩm mỗi trang
    paginator = Paginator(products, 12)
    page_number = request.GET.get('page')
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    # 6. Lấy các sản phẩm có Flash Sale đang hiệu lực
    flash_sale_products = Product.objects.filter(
        flash_sale__isnull=False,
        flash_sale__is_active=True,
        flash_sale__end_time__gt=timezone.now()
    ).select_related('flash_sale')

    # 7. Tin tức mới nhất
    try:
        from apps.core.models import NewsArticle
        latest_news = NewsArticle.objects.filter(is_published=True).order_by('-created_at')[:4]
    except ImportError:
        latest_news = []

    # 8. Truyền dữ liệu ra template
    context = {
        'products': page_obj,
        'page_obj': page_obj,
        'paginator': paginator,
        'categories': categories,
        'best_selling_products': best_selling_products,
        'current_category': current_category,
        'flash_sale_products': flash_sale_products,
        'latest_news': latest_news,
    }
    return render(request, 'client/home.html', context)

# =========================================
# 2. TÌM KIẾM SẢN PHẨM
# - search_view(): Tìm kiếm nâng cao (lọc danh mục, giá, tồn kho, sắp xếp)
# - api_search_autocomplete(): API gợi ý sản phẩm realtime (JSON)
# =========================================

def search_view(request):
    query = request.GET.get('q', '').strip()
    category_id = request.GET.get('category', '')
    min_price = request.GET.get('min_price', '')
    max_price = request.GET.get('max_price', '')
    sort = request.GET.get('sort', 'relevance')
    stock_filter = request.GET.get('stock', '')

    results = Product.objects.none()

    if query:
        # Ưu tiên: match tên trước, description sau
        name_match = Product.objects.filter(name__icontains=query)
        desc_match = Product.objects.filter(
            description__icontains=query
        ).exclude(name__icontains=query)
        results = (name_match | desc_match).distinct()
    else:
        results = Product.objects.all()

    # Lọc theo danh mục
    if category_id:
        results = results.filter(category_id=category_id)

    # Lọc theo khoảng giá
    if min_price and min_price.replace('.', '').isdigit():
        results = results.filter(price__gte=int(float(min_price)))
    if max_price and max_price.replace('.', '').isdigit():
        results = results.filter(price__lte=int(float(max_price)))

    # Lọc còn hàng
    if stock_filter == 'in_stock':
        results = results.filter(stock__gt=0)

    # Sắp xếp
    if sort == 'price_asc':
        results = results.order_by('price')
    elif sort == 'price_desc':
        results = results.order_by('-price')
    elif sort == 'newest':
        results = results.order_by('-created_at')
    else:
        results = results.order_by('-id')

    # Phân trang 12 sản phẩm / trang
    paginator = Paginator(results, 12)
    page_number = request.GET.get('page')
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    categories = Category.objects.all().order_by('name')

    # Build lại query string không có 'page' để dùng cho pagination link
    get_params = request.GET.copy()
    get_params.pop('page', None)
    query_string = get_params.urlencode()

    context = {
        'query': query,
        'results': page_obj,
        'page_obj': page_obj,
        'paginator': paginator,
        'total_count': paginator.count,
        'categories': categories,
        'current_category': category_id,
        'min_price': min_price,
        'max_price': max_price,
        'sort': sort,
        'stock_filter': stock_filter,
        'query_string': query_string,
    }
    return render(request, 'client/search_results.html', context)


def api_search_autocomplete(request):
    """API JSON trả về gợi ý sản phẩm cho thanh tìm kiếm realtime."""
    from django.urls import reverse as url_reverse
    q = request.GET.get('q', '').strip()
    if len(q) < 2:
        return JsonResponse({'suggestions': []})

    products = Product.objects.filter(name__icontains=q).order_by('-id')[:8]
    suggestions = []
    for p in products:
        suggestions.append({
            'id': p.id,
            'name': p.name,
            'price': int(p.price),
            'image': p.image.url if p.image else '',
            'url': url_reverse('client:product_detail', args=[p.id]),
            'category': p.category.name if p.category else '',
        })
    return JsonResponse({'suggestions': suggestions})

# =========================================
# 3. GIỎ HÀNG (CART)
# - cart_detail(): Xem giỏ hàng + áp dụng coupon
# - cart_add(): Thêm sản phẩm vào giỏ (hỗ trợ biến thể)
# - cart_remove(): Xóa sản phẩm khỏi giỏ
# - cart_update(): Cập nhật số lượng trong giỏ
# - apply_coupon(): Áp dụng mã giảm giá
# - remove_coupon(): Gỡ mã giảm giá
# =========================================

def cart_detail(request):
    cart = Cart(request)
    # Ép về Decimal ngay từ đầu cho chuẩn tiền tệ
    cart_total = Decimal(sum(item['price'] * item['quantity'] for item in cart))
    
    discount_amount = Decimal(0)
    final_total = cart_total
    coupon = None
    coupon_id = request.session.get('coupon_id')

    if coupon_id:
        try:
            coupon = Coupon.objects.get(id=coupon_id)
            if coupon.is_valid() and cart_total >= coupon.min_purchase:
                if coupon.discount_type == 'percent':
                    # Tính phần trăm trên kiểu Decimal
                    discount_amount = (cart_total * coupon.discount_value) / 100
                else:
                    discount_amount = coupon.discount_value
                
                discount_amount = min(discount_amount, cart_total)
                final_total = cart_total - discount_amount
            else:
                if 'coupon_id' in request.session:
                    del request.session['coupon_id']
                coupon = None
        except Coupon.DoesNotExist:
            if 'coupon_id' in request.session:
                del request.session['coupon_id']

    context = {
        'cart': cart,
        'cart_total': cart_total,
        'discount_amount': discount_amount,
        'final_total': final_total,
        'coupon': coupon
    }
    return render(request, 'client/cart.html', context)

def cart_add(request, product_id):
    cart = Cart(request)
    product = get_object_or_404(Product, id=product_id)
    
    qty = 1
    if request.method == 'POST':
        try: qty = int(request.POST.get('quantity', 1))
        except: qty = 1
        
    variation_id = request.POST.get('variation_id') if request.method == 'POST' else request.GET.get('variation_id')
    cart.add(product=product, quantity=qty, variation_id=variation_id)
    return redirect('client:cart')

def cart_remove(request, product_id):
    cart = Cart(request)
    product = get_object_or_404(Product, id=product_id)
    variation_id = request.POST.get('variation_id') if request.method == 'POST' else request.GET.get('variation_id')
    cart.remove(product, variation_id=variation_id)
    return redirect('client:cart')

# =========================================
# 4. CHI TIẾT SẢN PHẨM
# - product_detail(): Chi tiết SP + đánh giá + tồn kho cửa hàng + SP liên quan
# =========================================

def product_detail(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    
    # Xử lý khi Submit Form Đánh giá HOẶC Phản hồi Đánh giá (POST)
    if request.method == 'POST':
        if not request.user.is_authenticated:
            messages.error(request, "Bạn cần đăng nhập để thực hiện tính năng này.")
            return redirect('client:login')
            
        # 1. TRƯỜNG HỢP: Admin trả lời đánh giá
        review_id = request.POST.get('review_id')
        if review_id and (request.user.is_staff or getattr(request.user, 'profile', None) and request.user.profile.role in ['admin', 'staff', 'super_admin', 'store_admin']):
            admin_reply_text = request.POST.get('admin_reply')
            if admin_reply_text:
                review = get_object_or_404(Review, id=review_id)
                review.admin_reply = admin_reply_text
                from django.utils import timezone
                review.reply_created_at = timezone.now()
                review.save()
                messages.success(request, "Đã gửi câu trả lời thành công!")
            return redirect('client:product_detail', product_id=product.id)
            
        # 2. TRƯỜNG HỢP: Khách hàng viết Đánh giá mới
        rating = request.POST.get('rating')
        comment = request.POST.get('comment')
        
        if rating and comment:
            # Lưu đánh giá
            Review.objects.create(
                product=product,
                user=request.user,
                rating=int(rating),
                comment=comment
            )
            messages.success(request, "Đánh giá của bạn đã được ghi nhận!")
            return redirect('client:product_detail', product_id=product.id)

    # Lấy danh sách ảnh phụ của sản phẩm này
    product_images = product.images.all() 
    
    # Tải danh sách đánh giá của sản phẩm
    reviews = product.reviews.all()
    
    # Tính điểm trung bình
    avg_rating = 0
    if reviews.exists():
         avg_rating = sum(r.rating for r in reviews) / reviews.count()

    # Danh sách tồn kho tại các cửa hàng
    stores_stock_info = []
    stores = Store.objects.all()
    for store in stores:
        stock_record = StoreStock.objects.filter(store=store, product=product).first()
        quantity = stock_record.available_quantity if stock_record else 0
        stores_stock_info.append({
            'store_name': store.name,
            'address': store.address,
            'quantity': quantity,
            'in_stock': quantity > 0
        })

    # Gợi ý sản phẩm cùng danh mục
    related_products = Product.objects.filter(category=product.category).exclude(id=product.id)[:4]
    
    return render(request, 'client/product_detail.html', {
        'product': product,
        'product_images': product_images,
        'related_products': related_products,
        'reviews': reviews,
        'avg_rating': round(avg_rating, 1),
        'stores_stock_info': stores_stock_info,
    })

# =========================================
# 5. CỬA HÀNG (STORE LOCATOR)
# - store_locator(): Bản đồ cửa hàng + khoảng cách + trạng thái mở/đóng
# - api_search_stock(): API tìm cửa hàng có tồn kho theo keyword (JSON)
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
            'id': store.id,
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
# - checkout(): Trang thanh toán (coupon, giao hàng/nhận tại quán, tính phí ship, tạo đơn, gửi email)
# - payment_instruction_view(): Trang QR code thanh toán chuyển khoản
# - client_print_receipt(): In hóa đơn bán lẻ cho khách hàng
# =========================================
@login_required(login_url='client:login')
def checkout(request):
    cart = Cart(request)
    # Nếu giỏ hàng trống, không cho vào trang thanh toán
    if cart.get_total_price() == 0:
        return redirect('client:home')

    # ==========================================
    # 1. LOGIC TÍNH TOÁN MÃ GIẢM GIÁ
    # ==========================================
    cart_total = cart.get_total_price()
    discount_amount = 0
    coupon = None
    coupon_id = request.session.get('coupon_id')

    if coupon_id:
        try:
            coupon = Coupon.objects.get(id=coupon_id)
            if coupon.is_valid() and cart_total >= coupon.min_purchase:
                if coupon.discount_type == 'percent':
                    discount_amount = (cart_total * coupon.discount_value) / 100
                else:
                    discount_amount = coupon.discount_value
                discount_amount = min(discount_amount, cart_total)
            else:
                coupon = None
                if 'coupon_id' in request.session:
                    del request.session['coupon_id']
        except Coupon.DoesNotExist:
            coupon = None
            if 'coupon_id' in request.session:
                del request.session['coupon_id']
            
    final_total = cart_total - discount_amount

    # ==========================================
    # 2. XỬ LÝ LƯU ĐƠN HÀNG (KHI NGƯỜI DÙNG SUBMIT FORM)
    # ==========================================
    if request.method == 'POST':
        name = request.POST.get('fullname')
        phone = request.POST.get('phone')
        
        # Xử lý phương thức giao hàng
        delivery_method = request.POST.get('delivery_method', 'delivery')
        
        final_address = ""
        store_pickup = None
        shipping_fee = 0
        
        if delivery_method == 'delivery':
            address_id = request.POST.get('address_id', 'new')
            province_str = ""
            
            if address_id == 'new':
                province_str = request.POST.get('province', '')
                district = request.POST.get('district', '')
                ward = request.POST.get('ward', '')
                detail = request.POST.get('address_detail', '')
                final_address = f"{detail}, {ward}, {district}, {province_str}".strip(", ")
            else:
                try:
                    addr = ShippingAddress.objects.get(id=address_id, user=request.user)
                    province_str = addr.area_info or ""
                    final_address = f"{addr.address_detail}, {addr.area_info}".strip(", ")
                except ShippingAddress.DoesNotExist:
                    final_address = ""
            
            # Tính phí giao hàng
            province_lower = province_str.lower()
            is_hcm = any(x in province_lower for x in ['hcm', 'hồ chí minh', 'ho chi minh', 'hcmc'])
            nearby = ['bình dương', 'binh duong', 'đồng nai', 'dong nai', 'long an', 'bà rịa', 'ba ria', 'tây ninh', 'tay ninh', 'tiền giang', 'tien giang']
            is_nearby = any(x in province_lower for x in nearby)

            if is_hcm:
                if cart_total >= 500000:
                    shipping_fee = 0
                else:
                    shipping_fee = 30000
            elif is_nearby:
                shipping_fee = 30000
            else:
                shipping_fee = 50000
                
            final_total += shipping_fee
            
            # TỰ ĐỘNG GÁN KHO TỔNG LÀM CỬA HÀNG XUẤT KHO CHO ĐƠN GIAO TẬN NƠI
            store_pickup = Store.objects.filter(is_warehouse=True).first()
            
        elif delivery_method == 'pickup':
            # Nếu nhận tại cửa hàng, lưu ID cửa hàng khách chọn
            store_id = request.POST.get('store_id')
            if store_id:
                store_pickup = Store.objects.filter(id=store_id).first()
                final_address = f"Nhận tại cửa hàng: {store_pickup.name} ({store_pickup.address})"

        # Lấy hình thức thanh toán
        payment_method = request.POST.get('payment_method', 'cod')

        # Tạo Đơn hàng
        order = Order.objects.create(
            user=request.user if request.user.is_authenticated else None,
            full_name=name,
            phone=phone,
            address=final_address,
            total_price=final_total,             # Lưu giá ĐÃ TRỪ tiền giảm (cộng phí gửi)
            shipping_fee=shipping_fee,
            coupon=coupon,                       # Lưu ID mã giảm giá
            discount_amount=discount_amount,     # Lưu số tiền được giảm
            fulfillment_store=store_pickup,      # LƯU CỬA HÀNG CHỊU TRÁCH NHIỆM XUẤT KHO (Rất quan trọng)
            payment_method=payment_method,       # Hình thức thanh toán
            payment_status='unpaid'              # Khởi tạo mặc định
        )
        
        for item in cart:
            OrderItem.objects.create(
                order=order,
                product=item['product'],
                variation=item.get('variation'),
                price=item['price'],
                quantity=item['quantity']
            )
            
            # Tăng reserved_quantity (Hàng tạm giữ) tại kho phụ trách
            if store_pickup:
                store_stock = StoreStock.objects.filter(
                    store=store_pickup,
                    product=item['product'],
                    variation=item.get('variation')
                ).first()
                if store_stock:
                    store_stock.reserved_quantity += item['quantity']
                    store_stock.save()
            
        # Tăng lượt dùng của mã lên 1 và xóa mã khỏi session
        if coupon:
            coupon.used_count += 1
            coupon.save()
            del request.session['coupon_id']
            
        cart.clear()

        # ==================================================
        # TẠO THÔNG BÁO & GỬI EMAIL KHI ĐẶT HÀNG THÀNH CÔNG
        # ==================================================
        if request.user.is_authenticated:
            Notification.objects.create(
                user=request.user,
                notif_type='order_placed',
                order=order,
                message=f'Đơn hàng #{order.id} của bạn đã được đặt thành công! Chúng tôi đang xác nhận đơn hàng.'
            )
            # Gửi email xác nhận đặt hàng
            try:
                items_with_total = [
                    {
                        'name': item.product.name,
                        'quantity': item.quantity,
                        'price': item.price,
                        'subtotal': item.price * item.quantity,
                    }
                    for item in order.items.all()
                ]
                html_order = render_to_string('client/emails/order_placed_email.html', {
                    'order': order,
                    'items': items_with_total,
                    'username': request.user.username,
                })
                send_mail(
                    subject=f'✅ Đặt hàng thành công - Đơn #{order.id} | Phone Store',
                    message=strip_tags(html_order),
                    from_email='noreply@phonestore.vn',
                    recipient_list=[request.user.email],
                    html_message=html_order,
                    fail_silently=True,
                )
            except Exception:
                pass

        messages.success(request, f"🎉 Đặt hàng thành công! Đơn hàng <strong>#{order.id}</strong> đang được xử lý.")
        if payment_method == 'bank_transfer':
            return redirect('client:payment_instruction', order_id=order.id)
            
        return redirect('client:notifications')

    # ==========================================
    # 3. TRUYỀN DỮ LIỆU RA GIAO DIỆN (GET)
    # ==========================================
    saved_addresses = ShippingAddress.objects.filter(user=request.user).order_by('-is_default')
    
    # KHO TỔNG: Kiểm tra xem có đủ hàng để ship tận nhà không
    main_warehouse = Store.objects.filter(is_warehouse=True).first()
    can_home_delivery = True
    
    if main_warehouse:
        for item in cart:
            product = item['product']
            quantity_needed = item['quantity']
            inventory = StoreStock.objects.filter(store=main_warehouse, product=product).first()
            if not inventory or inventory.available_quantity < quantity_needed:
                can_home_delivery = False
                break
    else:
        can_home_delivery = False

    # CHI NHÁNH: Kiểm tra tồn kho từng cửa hàng để Nhận tại quán
    stores = Store.objects.all()
    for store in stores:
        store.has_stock = True 
        for item in cart:
            product = item['product']
            quantity_needed = item['quantity']
            inventory = StoreStock.objects.filter(store=store, product=product).first()
            if not inventory or inventory.available_quantity < quantity_needed:
                store.has_stock = False
                break

    context = {
        'cart': cart,
        'cart_total': cart_total,
        'discount_amount': discount_amount,
        'final_total': final_total,
        'coupon': coupon,
        'saved_addresses': saved_addresses,
        'stores': stores,
        'can_home_delivery': can_home_delivery,
    }
    return render(request, 'client/checkout.html', context)

# (Thuộc section 6 - THANH TOÁN)
def payment_instruction_view(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    
    # Chỉ cho phép ở trạng thái chờ thanh toán
    if order.payment_status == 'paid':
        messages.info(request, "Đơn hàng này đã được thanh toán rồi.")
        return redirect('client:my_orders')
        
    if request.method == 'POST':
        receipt = request.FILES.get('payment_receipt')
        if receipt:
            order.payment_receipt = receipt
            order.save()
            messages.success(request, "Đã gửi URL hình ảnh biên lai thành công. Chúng tôi sẽ đối soát và xử lý đơn hàng sớm nhất.")
            return redirect('client:my_orders') if request.user.is_authenticated else redirect('client:cart')
        else:
            messages.error(request, "Vui lòng chọn hình ảnh chụp biên lai giao dịch.")
            
    # Tạo API QR Code của VietQR (Miễn phí)
    # Cấu trúc: https://img.vietqr.io/image/<BANK_ID>-<ACCOUNT_NO>-<TEMPLATE>.png?amount=<AMOUNT>&addInfo=<DESCRIPTION>&accountName=<ACCOUNT_NAME>
    # Giả lập thông tin Bank của chủ shop
    bank_id = "mb" # MB Bank (ví dụ Mbbank, Vietinbank, v.v...)
    account_no = "123456789"
    account_name = "NGUYEN VAN A"
    amount = int(order.total_price)
    description = f"THANH TOAN DON HANG {order.id}"
    
    qr_code_url = f"https://img.vietqr.io/image/{bank_id}-{account_no}-compact.png?amount={amount}&addInfo={description}&accountName={account_name}"

    context = {
        'order': order,
        'qr_code_url': qr_code_url,
        'bank_id': bank_id,
        'account_no': account_no,
        'account_name': account_name,
        'amount': amount,
        'description': description
    }
    return render(request, 'client/payment_instruction.html', context)


# (Thuộc section 6 - IN HÓA ĐƠN BÁN LẺ)
@login_required(login_url='client:login')
def client_print_receipt(request, order_id):
    """
    View cho phép khách hàng in hóa đơn bán lẻ sau khi đơn hàng đã được
    thanh toán thành công (payment_status='paid') hoặc là đơn COD đã hoàn thành.
    """
    order = get_object_or_404(Order, id=order_id, user=request.user)

    # Chỉ cho phép in hóa đơn khi:
    # 1. Đã thanh toán thành công (bank transfer đã xác nhận), HOẶC
    # 2. Là đơn COD và đã hoàn thành
    can_print = (
        order.payment_status == 'paid' or
        (order.payment_method == 'cod' and order.status == 'completed')
    )

    if not can_print:
        messages.warning(
            request,
            "⚠️ Hóa đơn chỉ được in sau khi đơn hàng đã được thanh toán hoặc giao thành công."
        )
        return redirect('client:order_detail', order_id=order.id)

    order_items = order.items.select_related('product', 'variation').all()
    subtotal = sum(item.price * item.quantity for item in order_items)

    context = {
        'order': order,
        'order_items': order_items,
        'subtotal': subtotal,
        'store': order.fulfillment_store,
    }
    return render(request, 'client/receipt_print.html', context)


# =========================================
# 7. TÀI KHOẢN & XÁC THỰC
# - register_view(): Đăng ký tài khoản (gửi email xác thực)
# - verification_pending(): Trang nhắc kiểm tra email
# - verify_email(): Xác thực email qua link token
# - login_view(): Đăng nhập (phân luồng admin/khách)
# - logout_view(): Đăng xuất
# - forgot_password(): Quên mật khẩu (gửi email reset)
# - resend_verification(): Gửi lại email xác thực
# - reset_password(): Đặt lại mật khẩu từ link email
# =========================================

def register_view(request):
    if request.method == 'POST':
        u = request.POST.get('username')
        e = request.POST.get('email')
        p = request.POST.get('password')
        cp = request.POST.get('confirm_password')
        
        if User.objects.filter(username=u).exists():
            messages.error(request, "Tên đăng nhập đã tồn tại")
        elif User.objects.filter(email=e).exists():
            messages.error(request, "Email này đã được sử dụng")
        elif p != cp:
            messages.error(request, "Mật khẩu xác nhận không khớp")
        else:
            # Tạo tài khoản nhưng CHƯ A KÍCH HOẠT — chờ xác thực email
            user = User.objects.create_user(username=u, email=e, password=p, is_active=False)
            # Tạo token và uid xác thực
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            verify_link = request.build_absolute_uri(
                reverse('client:verify_email', kwargs={'uidb64': uid, 'token': token})
            )
            # Gửi email xác thực qua Mailtrap
            try:
                html_message = render_to_string('client/emails/verify_email.html', {
                    'username': u,
                    'verify_link': verify_link,
                })
                send_mail(
                    subject='✉️ Xác thực email - Phone Store',
                    message=strip_tags(html_message),
                    from_email='noreply@phonestore.vn',
                    recipient_list=[e],
                    html_message=html_message,
                    fail_silently=False,
                )
            except Exception as ex:
                # Nếu không gửi được email, xóa user và báo lỗi
                user.delete()
                messages.error(request, f"Không thể gửi email xác thực. Vui lòng thử lại. ({ex})")
                return render(request, 'client/register.html')
            # Chuyển đến trang nhắc nhở kiểm tra email (chưa login)
            return redirect(reverse('client:verification_pending') + f'?email={e}')
    return render(request, 'client/register.html')


def verification_pending(request):
    """Trang thông báo kiểm tra email sau khi đăng ký."""
    email = request.GET.get('email', '')
    return render(request, 'client/verification_pending.html', {'email': email})


def verify_email(request, uidb64, token):
    """Xác thực email: kích hoạt tài khoản khi click link."""
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        if user.is_active:
            messages.info(request, "Tài khoản đã được xác thực trước đó. Vui lòng đăng nhập.")
            return redirect('client:login')
        # Kích hoạt tài khoản
        user.is_active = True
        user.save()
        # Gửi email chào mừng sau khi xác thực thành công
        try:
            html_welcome = render_to_string('client/emails/welcome_email.html', {
                'username': user.username,
                'email': user.email,
            })
            send_mail(
                subject='🎉 Chào mừng bạn đến với Phone Store!',
                message=strip_tags(html_welcome),
                from_email='noreply@phonestore.vn',
                recipient_list=[user.email],
                html_message=html_welcome,
                fail_silently=True,
            )
        except Exception:
            pass
        messages.success(request, f"🎉 Tài khoản <strong>{user.username}</strong> đã được kích hoạt! Hãy đăng nhập.")
        return redirect('client:login')
    else:
        return render(request, 'client/verification_failed.html')


# (Thuộc section 7 - QUÊN MẬT KHẨU)

def forgot_password(request):
    """Bước 1: Nhập email để nhận link đặt lại mật khẩu."""
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        try:
            user = User.objects.get(email=email)
            # Tạo token và uid
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            reset_link = request.build_absolute_uri(
                reverse('client:reset_password', kwargs={'uidb64': uid, 'token': token})
            )
            # Gửi email đặt lại mật khẩu
            html_message = render_to_string('client/emails/reset_password_email.html', {
                'username': user.username,
                'reset_link': reset_link,
            })
            send_mail(
                subject='🔒 Đặt lại mật khẩu - Phone Store',
                message=strip_tags(html_message),
                from_email='noreply@phonestore.vn',
                recipient_list=[email],
                html_message=html_message,
                fail_silently=False,
            )
            messages.success(request, f"Link đặt lại mật khẩu đã được gửi đến {email}. Vui lòng kiểm tra hộp thư.")
        except User.DoesNotExist:
            # Vẫn thông báo thành công để bảo mật (không lộ email có tồn tại không)
            messages.success(request, f"Nếu email {email} tồn tại trong hệ thống, bạn sẽ nhận được link đặt lại mật khẩu.")
        except Exception as ex:
            messages.error(request, f"Không thể gửi email. Lỗi: {ex}")
        return redirect('client:forgot_password')
    return render(request, 'client/forgot_password.html')


def resend_verification(request):
    """Gửi lại email xác thực cho tài khoản chưa active."""
    email = request.GET.get('email', '').strip()
    if not email:
        messages.error(request, "Email không hợp lệ.")
        return redirect('client:login')
    try:
        user = User.objects.get(email=email, is_active=False)
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        verify_link = request.build_absolute_uri(
            reverse('client:verify_email', kwargs={'uidb64': uid, 'token': token})
        )
        html_message = render_to_string('client/emails/verify_email.html', {
            'username': user.username,
            'verify_link': verify_link,
        })
        send_mail(
            subject='✉️ Xác thực email - Phone Store',
            message=strip_tags(html_message),
            from_email='noreply@phonestore.vn',
            recipient_list=[email],
            html_message=html_message,
            fail_silently=False,
        )
        messages.success(request, f"Đã gửi lại email xác thực đến {email}. Vui lòng kiểm tra hộp thư.")
    except User.DoesNotExist:
        messages.error(request, "Không tìm thấy tài khoản chưa xác thực với email này.")
    except Exception as ex:
        messages.error(request, f"Không thể gửi email: {ex}")
    return redirect('client:login')


def reset_password(request, uidb64, token):
    """Bước 2: Đặt mật khẩu mới từ link email."""
    # Giải mã uid và lấy user
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    token_valid = user is not None and default_token_generator.check_token(user, token)

    if request.method == 'POST':
        if not token_valid:
            messages.error(request, "Link đặt lại mật khẩu không hợp lệ hoặc đã hết hạn.")
            return redirect('client:forgot_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        if not new_password or len(new_password) < 8:
            messages.error(request, "Mật khẩu phải có ít nhất 8 ký tự.")
        elif new_password != confirm_password:
            messages.error(request, "Hai mật khẩu không khớp nhau.")
        else:
            user.set_password(new_password)
            user.save()
            messages.success(request, "Đặt lại mật khẩu thành công! Vui lòng đăng nhập.")
            return redirect('client:login')
        return render(request, 'client/reset_password.html', {'token_valid': token_valid, 'uidb64': uidb64, 'token': token})

    return render(request, 'client/reset_password.html', {
        'token_valid': token_valid,
        'uidb64': uidb64,
        'token': token,
    })

def login_view(request):
    # Lấy tham số 'next' từ URL (nếu có)
    next_url = request.GET.get('next')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        # Kiểm tra user tồn tại nhưng chưa xác thực email
        try:
            unverified = User.objects.get(username=username)
            if not unverified.is_active and unverified.check_password(password):
                messages.warning(
                    request,
                    f'⚠️ Tài khoản chưa được xác thực! '
                    f'Vui lòng kiểm tra hộp thư <strong>{unverified.email}</strong> '
                    f'và click vào link xác thực. '
                    f'<a href="{ reverse("client:resend_verification") }?email={unverified.email}" '
                    f'class="alert-link">Gửi lại email?</a>'
                )
                return render(request, 'client/login.html')
        except User.DoesNotExist:
            pass
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            
            # Nếu là Admin
            if user.is_staff or user.is_superuser:
                messages.success(request, f"Chào Admin {user.username}!")
                return redirect('client:admin_dashboard') 
            
            # Nếu là Khách hàng bình thường
            else:
                # Nếu có đường dẫn 'next' -> Trả về trang đó
                if next_url:
                    return redirect(next_url)
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

@login_required(login_url='client:login')
def request_return_view(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    
    if order.status != 'completed':
        messages.error(request, "Đơn hàng chưa hoàn thành, không thể trả hàng.")
        return redirect('client:my_orders')

    if order.returns.exclude(status='rejected').exists():
        messages.warning(request, "Bạn đã gửi yêu cầu trả hàng cho đơn này rồi.")
        return redirect('client:return_history')

    if request.method == 'POST':
        reason = request.POST.get('reason')
        proof_image = request.FILES.get('proof_image')
        
        if not proof_image:
            messages.error(request, "Vui lòng đính kèm hình ảnh bằng chứng.")
            return render(request, 'client/return_request_form.html', {'order': order})

        return_req = ReturnRequest.objects.create(
            order=order,
            user=request.user,
            reason=reason,
            proof_image=proof_image,
            refund_amount=order.total_price  # Hoàn 100%
        )
        
        # Mặc định tạo item trả toàn bộ số lượng của đơn hàng
        for item in order.items.all():
            ReturnItem.objects.create(
                return_request=return_req,
                order_item=item,
                quantity=item.quantity
            )
            
        messages.success(request, "Đã gửi yêu cầu trả hàng. Vui lòng chờ phản hồi.")
        return redirect('client:return_history')
        
    return render(request, 'client/return_request_form.html', {'order': order})

@login_required(login_url='client:login')
def return_history_view(request):
    returns = ReturnRequest.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'client/return_history.html', {'returns': returns})


def error_404(request, exception):
    return render(request, '404.html', status=404)

def apply_coupon(request):
    if request.method == 'POST':
        code = request.POST.get('coupon_code')
        # Giả sử bạn có một hàm tính tổng tiền giỏ hàng hiện tại (thay get_cart_total() bằng biến tổng tiền thật của bạn)
        # Ví dụ: cart = request.session.get('cart', {}) ... cart_total = sum(...)
        cart_total = 10000000 # <-- BẠN CẦN THAY CHỖ NÀY BẰNG TỔNG TIỀN THẬT TRONG GIỎ HÀNG CỦA KHÁCH
        
        try:
            coupon = Coupon.objects.get(code__iexact=code)
            
            # Kiểm tra tính hợp lệ
            if not coupon.is_valid():
                messages.error(request, "Mã giảm giá đã hết hạn, bị vô hiệu hóa hoặc hết lượt sử dụng.")
            elif cart_total < coupon.min_purchase:
                messages.error(request, f"Đơn hàng phải từ {coupon.min_purchase:,.0f}đ để áp dụng mã này.")
            else:
                # Nếu hợp lệ, lưu ID của mã vào session
                request.session['coupon_id'] = coupon.id
                messages.success(request, f"Áp dụng mã {coupon.code} thành công!")
                
        except Coupon.DoesNotExist:
            messages.error(request, "Mã giảm giá không tồn tại.")
            
    return redirect('client:cart') # Hoặc đổi thành 'client:checkout' tùy nơi bạn đặt ô nhập mã

def remove_coupon(request):
    if 'coupon_id' in request.session:
        del request.session['coupon_id']
        messages.info(request, "Đã gỡ mã giảm giá.")
    return redirect('client:cart')

def cart_update(request, product_id, quantity):
    cart = Cart(request)
    product = get_object_or_404(Product, id=product_id)
    variation_id = request.GET.get('variation_id')
    
    # Cập nhật số lượng mới (ghi đè số lượng cũ)
    if quantity > 0:
        cart.add(product=product, quantity=quantity, override_quantity=True, variation_id=variation_id)
        messages.success(request, f"Đã cập nhật số lượng cho {product.name}")
    else:
        cart.remove(product, variation_id=variation_id) # Nếu số lượng = 0 thì xóa khỏi giỏ
        
    return redirect('client:cart')

@login_required
def user_account(request):
    user = request.user
    profile = user.profile

    # --- XỬ LÝ CÁC YÊU CẦU POST (LƯU DỮ LIỆU) ---
    if request.method == 'POST':
        action = request.POST.get('action')

        # 1. Xử lý cập nhật thông tin cá nhân
        if action == 'update_profile' or not action:
            email = request.POST.get('email')
            full_name = request.POST.get('full_name', '').strip()
            phone = request.POST.get('phone')
            address = request.POST.get('address')
            avatar = request.FILES.get('avatar')

            user.email = email
            if ' ' in full_name:
                user.last_name = full_name.rsplit(' ', 1)[-1]
                user.first_name = full_name.rsplit(' ', 1)[0]
            else:
                user.first_name = full_name
                user.last_name = ''
            user.save()

            profile.phone = phone
            profile.address = address
            if avatar:
                profile.avatar = avatar
            profile.save()

            messages.success(request, 'Cập nhật thông tin cá nhân thành công!')
            return redirect(reverse('client:user_account') + '?tab=profile')

        # 2. Xử lý thêm địa chỉ mới
        elif action == 'add_address':
            receiver_name = request.POST.get('receiver_name')
            phone_number = request.POST.get('phone_number')
            area_info = request.POST.get('area_info')
            address_detail = request.POST.get('address_detail')
            is_default = 'is_default' in request.POST

            ShippingAddress.objects.create(
                user=user,
                receiver_name=receiver_name,
                phone_number=phone_number,
                area_info=area_info,
                address_detail=address_detail,
                is_default=is_default
            )
            messages.success(request, 'Đã thêm địa chỉ mới vào sổ địa chỉ!')
            return redirect(reverse('client:user_account') + '?tab=profile')

        # 3. Xử lý xóa địa chỉ
        elif action == 'delete_address':
            address_id = request.POST.get('address_id')
            if address_id:
                try:
                    address = ShippingAddress.objects.get(id=address_id, user=user)
                    address.delete()
                    messages.success(request, 'Đã xóa địa chỉ thành công!')
                except ShippingAddress.DoesNotExist:
                    messages.error(request, 'Địa chỉ không tồn tại hoặc bạn không có quyền xóa.')
            return redirect(reverse('client:user_account') + '?tab=profile')

        # 4. Xử lý đổi mật khẩu
        elif action == 'change_password':
            old_pass = request.POST.get('old_password')
            new_pass = request.POST.get('new_password')
            confirm_pass = request.POST.get('confirm_password')

            if not user.check_password(old_pass):
                messages.error(request, 'Mật khẩu hiện tại không chính xác.')
                return redirect(reverse('client:user_account') + '?tab=profile&pwd_error=old')
            elif new_pass != confirm_pass:
                messages.error(request, 'Mật khẩu mới không khớp.')
                return redirect(reverse('client:user_account') + '?tab=profile&pwd_error=mismatch')
            elif len(new_pass) < 6:
                messages.error(request, 'Mật khẩu mới phải có ít nhất 6 ký tự.')
                return redirect(reverse('client:user_account') + '?tab=profile&pwd_error=length')
            else:
                user.set_password(new_pass)
                user.save()
                update_session_auth_hash(request, user)  # Giữ user ở trạng thái đăng nhập
                messages.success(request, 'Đã đổi mật khẩu thành công!')
                return redirect(reverse('client:user_account') + '?tab=profile&pwd_success=true')

        # 4. Xử lý xóa tài khoản
        elif action == 'delete_account':
            # Thực hiện xóa mềm hoặc xóa cứng tùy chính sách, ở đây là xóa cứng
            user.delete()
            messages.warning(request, 'Tài khoản của bạn đã được xóa khỏi hệ thống.')
            return redirect('client:home')

    # --- XỬ LÝ LẤY DỮ LIỆU HIỂN THỊ (GET) ---
    
    # 1. Lấy danh sách đơn hàng và lọc (Code cũ)
    orders = Order.objects.filter(user=request.user).order_by('-created_at')

    status_filter = request.GET.get('status', 'all')
    if status_filter != 'all':
        orders = orders.filter(status=status_filter)

    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    if start_date_str and end_date_str:
        start_date = parse_date(start_date_str)
        end_date = parse_date(end_date_str)
        if start_date and end_date:
            orders = orders.filter(created_at__date__gte=start_date, created_at__date__lte=end_date)

    # 2. Lấy danh sách sổ địa chỉ (Chức năng mới)
    addresses = user.shipping_addresses.all().order_by('-is_default', '-id')

    context = {
        'profile': profile,
        'orders': orders,
        'addresses': addresses,
        'rank': profile.rank,
        'next_threshold': profile.next_rank_threshold,
        'current_status': status_filter,
        'start_date': start_date_str,
        'end_date': end_date_str,
        'today': timezone.now(),
        'rank_data': [
            ('NEW', '#d70018', 'fa-star'),
            ('MEMBER', '#d70018', 'fa-award'),
            ('SILVER', '#adb5bd', 'fa-medal'),
            ('GOLD', '#ffc107', 'fa-crown'),
        ]
    }
    return render(request, 'client/account_dashboard.html', context)


# =========================================
# 8. TÀI KHOẢN KHÁCH HÀNG & ĐƠN HÀNG
# - my_orders(): Danh sách đơn hàng của tôi
# - order_detail(): Chi tiết đơn hàng khách hàng
# - cancel_order(): Hủy đơn hàng (chỉ khi pending)
# - request_return_view(): Gửi yêu cầu trả hàng
# - return_history_view(): Lịch sử trả hàng
# - user_account(): Dashboard tài khoản (profile, địa chỉ, đổi mật khẩu, xóa TK)
# - error_404(): Trang lỗi 404
# - feedback_view(): Gửi ý kiến / liên hệ (email admin + khách)
# =========================================
def feedback_view(request):
    """Trang gửi ý kiến / liên hệ của khách hàng."""
    from apps.core.models import Feedback
    from django.conf import settings as django_settings

    if request.method == 'POST':
        name    = request.POST.get('name', '').strip()
        email   = request.POST.get('email', '').strip()
        phone   = request.POST.get('phone', '').strip()
        topic   = request.POST.get('topic', 'other')
        message = request.POST.get('message', '').strip()

        if not name or not email or not message:
            messages.error(request, "Vui lòng điền đầy đủ thông tin bắt buộc.")
            return render(request, 'client/feedback.html', {
                'form_data': request.POST,
                'topics': Feedback.TOPIC_CHOICES,
            })

        # Lưu vào database
        fb = Feedback.objects.create(
            user    = request.user if request.user.is_authenticated else None,
            name    = name,
            email   = email,
            phone   = phone,
            topic   = topic,
            message = message,
        )

        # --- Email 1: Thông báo đến Admin ---
        try:
            admin_html = render_to_string('client/emails/feedback_admin.html', {
                'name':    name,
                'email':   email,
                'phone':   phone,
                'topic':   fb.get_topic_display(),
                'message': message,
                'fb_id':   fb.id,
            })
            admin_email = getattr(django_settings, 'ADMIN_EMAIL', django_settings.EMAIL_HOST_USER)
            send_mail(
                subject=f'[Phone Store] Ý kiến mới #{fb.id} - {fb.get_topic_display()}',
                message=strip_tags(admin_html),
                from_email=django_settings.DEFAULT_FROM_EMAIL,
                recipient_list=[admin_email],
                html_message=admin_html,
                fail_silently=True,
            )
        except Exception:
            pass

        # --- Email 2: Xác nhận gửi thành công đến khách ---
        try:
            customer_html = render_to_string('client/emails/feedback_customer.html', {
                'name':    name,
                'topic':   fb.get_topic_display(),
                'message': message,
                'fb_id':   fb.id,
            })
            send_mail(
                subject='✅ Phone Store đã nhận ý kiến của bạn!',
                message=strip_tags(customer_html),
                from_email=django_settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                html_message=customer_html,
                fail_silently=True,
            )
        except Exception:
            pass

        messages.success(request, "🎉 Cảm ơn bạn đã gửi ý kiến! Chúng tôi sẽ phản hồi sớm nhất có thể.")
        return redirect('client:feedback')

    return render(request, 'client/feedback.html', {
        'topics': Feedback.TOPIC_CHOICES,
    })


# =========================================
# 9. THÔNG BÁO ĐƠN HÀNG (NOTIFICATIONS)
# - notifications_list(): Danh sách thông báo (đánh dấu đã đọc)
# - mark_notification_read(): Đánh dấu 1 thông báo đã đọc
# - mark_all_notifications_read(): Đánh dấu tất cả đã đọc
# =========================================

@login_required(login_url='client:login')
def notifications_list(request):
    """Trang hiển thị tất cả thông báo của người dùng."""
    notifications = Notification.objects.filter(user=request.user).select_related('order')
    # Đếm theo loại trước khi đánh dấu đã đọc
    placed_count   = notifications.filter(notif_type='order_placed').count()
    shipped_count  = notifications.filter(notif_type='order_shipped').count()
    completed_count = notifications.filter(notif_type='order_completed').count()
    # Đánh dấu tất cả là đã đọc khi vào trang
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return render(request, 'client/notifications.html', {
        'notifications': notifications,
        'placed_count': placed_count,
        'shipped_count': shipped_count,
        'completed_count': completed_count,
    })


@login_required(login_url='client:login')
def mark_notification_read(request, pk):
    """Đánh dấu một thông báo là đã đọc và redirect đến trang đơn hàng liên quan."""
    notif = get_object_or_404(Notification, pk=pk, user=request.user)
    notif.is_read = True
    notif.save()
    if notif.order:
        return redirect('client:order_detail', order_id=notif.order.id)
    return redirect('client:notifications')


@login_required(login_url='client:login')
def mark_all_notifications_read(request):
    """Đánh dấu tất cả thông báo là đã đọc."""
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return redirect('client:notifications')


# =========================================
# 10. TRANG CHÍNH SÁCH (STATIC PAGES)
# - policy_warranty(): Chính sách bảo hành
# - policy_return(): Chính sách đổi trả
# - policy_guide(): Hướng dẫn mua hàng
# =========================================

def policy_warranty(request):
    """Trang chính sách bảo hành."""
    return render(request, 'client/policy_warranty.html')

def policy_return(request):
    """Trang chính sách đổi trả."""
    return render(request, 'client/policy_return.html')

def policy_guide(request):
    """Trang hướng dẫn mua hàng."""
    return render(request, 'client/policy_guide.html')

# =========================================
# 11. AI CHAT API
# - ai_chat_api(): API chatbot AI (Groq/Llama) hỗ trợ khách hàng
# =========================================
import json
import os
from django.http import JsonResponse

def ai_chat_api(request):
    """API xử lý tin nhắn chat từ khách hàng bằng AI Gemini."""
    if request.method == 'POST':
        try:
            from groq import Groq
            from django.conf import settings
            data = json.loads(request.body)
            message = data.get('message', '')
            
            # Lấy API Key từ cài đặt trong file settings.py
            api_key = getattr(settings, 'GROQ_API_KEY', '')
            if not api_key:
                return JsonResponse({'response': 'Hệ thống AI chưa được cấu hình API Key. Quản trị viên vui lòng thiết lập biến GROQ_API_KEY trong file settings.py.'})

            # Cảnh báo nếu API key sai định dạng
            if not api_key.startswith('gsk_'):
                return JsonResponse({'response': 'Lỗi: API Key Groq phải bắt đầu bằng chữ "gsk_". Vui lòng kiểm tra lại key của bạn.'})

            client = Groq(api_key=api_key)
            
            # Prompts hệ thống để AI đóng vai nhân viên
            system_prompt = "Bạn là trợ lý ảo tên là PhoneBot của cửa hàng điện thoại uy tín mang tên Phone Store. Hãy trả lời thật ngắn gọn, lịch sự, đúng trọng tâm bằng tiếng Việt (tối đa 3 câu)."
            
            # Sử dụng model llama-3.3-70b-versatile mới nhất của Meta trên server Groq 
            chat_completion = client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {
                        "role": "user",
                        "content": message,
                    }
                ],
                model="llama-3.3-70b-versatile",
            )
            
            bot_reply = chat_completion.choices[0].message.content
            return JsonResponse({'response': bot_reply})
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Invalid method. Only POST allowed.'}, status=405)

# (Thuộc section 5 - API TÌM KIẾM TỒN KHO STORE LOCATOR)
def api_search_stock(request):
    """
    Nhận tham số ?q=<keyword>, tìm các Store có sản phẩm chứa keyword và số lượng tồn kho > 0.
    Trả về: {"status": "ok", "stores": [1, 2, 4]}  (danh sách ID các cửa hàng có hàng)
    """
    q = request.GET.get('q', '').strip()
    if not q:
        return JsonResponse({'status': 'empty', 'stores': []})
    
    # Tìm sản phẩm theo keyword
    products = Product.objects.filter(name__icontains=q)
    if not products.exists():
        return JsonResponse({'status': 'not_found', 'stores': []})
    
    # Tìm những cửa hàng có stock > 0 cho các sản phẩm này
    store_ids = StoreStock.objects.filter(product__in=products, quantity__gt=0).values_list('store_id', flat=True).distinct()
    
    return JsonResponse({'status': 'ok', 'stores': list(store_ids)})

# =========================================
# 12. TIN TỨC (NEWS / BLOG)
# - news_list(): Danh sách bài viết (lọc danh mục, phân trang, sidebar)
# - news_detail(): Chi tiết bài viết (tăng view, bình luận, bài liên quan)
# =========================================
def news_list(request):
    from apps.core.models import NewsArticle, NewsCategory, Event, YoutubeVideo
    from django.core.paginator import Paginator
    from django.utils import timezone
    
    qs = NewsArticle.objects.filter(is_published=True).order_by('-is_pinned', '-created_at')
    
    # Filter
    cat_slug = request.GET.get('category')
    if cat_slug:
        qs = qs.filter(category__slug=cat_slug)
        
    # Phân trang
    paginator = Paginator(qs, 9)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Sidebar
    categories = NewsCategory.objects.all()
    trending_news = NewsArticle.objects.filter(is_published=True).order_by('-views')[:5]
    latest_news = NewsArticle.objects.filter(is_published=True).order_by('-created_at')[:3]
    
    # Sự kiện sắp tới (chỉ lấy active + chưa qua ngày)
    upcoming_events = Event.objects.filter(
        is_active=True, event_date__gte=timezone.now().date()
    ).order_by('event_date')[:5]
    
    # Video YouTube (chỉ lấy active)
    youtube_videos = YoutubeVideo.objects.filter(is_active=True).order_by('display_order')[:10]
    
    context = {
        'page_obj': page_obj,
        'categories': categories,
        'trending_news': trending_news,
        'latest_news': latest_news,
        'current_cat': cat_slug,
        'upcoming_events': upcoming_events,
        'youtube_videos': youtube_videos,
    }
    return render(request, 'client/news_list.html', context)

def news_detail(request, slug):
    from apps.core.models import NewsArticle, NewsComment
    article = get_object_or_404(NewsArticle, slug=slug, is_published=True)
    
    # Tăng lượt xem
    article.views += 1
    article.save(update_fields=['views'])
    
    # Xử lý comment
    if request.method == 'POST' and request.user.is_authenticated:
        content = request.POST.get('content')
        if content:
            NewsComment.objects.create(
                article=article,
                user=request.user,
                content=content
            )
            messages.success(request, 'Bình luận của bạn đã được gửi.')
            return redirect('client:news_detail', slug=slug)
            
    comments = article.comments.all()
    if article.category:
        related_articles = NewsArticle.objects.filter(
            category=article.category, is_published=True
        ).exclude(id=article.id).order_by('-created_at')[:5]
    else:
        related_articles = NewsArticle.objects.filter(
            is_published=True
        ).exclude(id=article.id).order_by('-created_at')[:5]
    from apps.core.models import NewsCategory
    categories = NewsCategory.objects.all()
    
    context = {
        'article': article,
        'comments': comments,
        'related_articles': related_articles,
        'categories': categories,
    }
    return render(request, 'client/news_detail.html', context)

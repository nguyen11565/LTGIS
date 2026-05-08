from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Sum
from django.db.models.functions import TruncDate, TruncMonth
from django.utils.text import slugify
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import transaction
from django.http import JsonResponse
from django.core.exceptions import ObjectDoesNotExist
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

# 1. Import models từ core
from apps.core.models import Region, Store, Product, Order, Category, OrderItem, StockTransaction, ProductImage, Coupon, FlashSale, StoreStock, Notification, StockTransfer, StockTransferItem, Stocktaking, StocktakingItem, ProductVariation
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings as django_settings

# 2. Import models bổ sung (Try/Except để tránh lỗi không tìm thấy bảng)
try:
    from apps.core.models import UserProfile, StoreStock, FlashSale, Coupon
except ImportError:
    from .models import UserProfile, StoreStock, FlashSale, Coupon

# 3. Import Decorator bảo mật tự làm
from .decorators import role_required

# 4. Helper: Phân trang & Preserved Filters
ITEMS_PER_PAGE = 15

def paginate_qs(request, queryset, per_page=ITEMS_PER_PAGE):
    """Phân trang queryset. Trả về (page_obj, preserved_filters)"""
    paginator = Paginator(queryset, per_page)
    page_number = request.GET.get('page')
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)
    
    # Preserve existing GET params (trừ 'page') cho pagination links
    params = request.GET.copy()
    if 'page' in params:
        del params['page']
    preserved = params.urlencode()
    
    return page_obj, preserved

# =========================================
# 1. DASHBOARD & THỐNG KÊ
# - dashboard(): Trang tổng quan (thống kê, biểu đồ doanh thu)
# - export_monthly_revenue_excel(): Xuất báo cáo doanh thu theo tháng ra Excel
# =========================================
@role_required(['super_admin', 'regional_manager', 'store_admin', 'warehouse_keeper', 'sales_staff'])
def dashboard(request):
    profile = request.user.profile

    # === BASE QUERYSET (data scoping theo role) ===
    if profile.role == 'super_admin':
        base_orders = Order.objects.all()
        base_stores = Store.objects.all()
        base_stock = StoreStock.objects.all()
    elif profile.role == 'regional_manager':
        base_orders = Order.objects.filter(fulfillment_store__region=profile.region)
        base_stores = Store.objects.filter(region=profile.region)
        base_stock = StoreStock.objects.filter(store__region=profile.region)
    else:
        if profile.store:
            base_orders = Order.objects.filter(fulfillment_store=profile.store)
            base_stores = Store.objects.filter(id=profile.store_id)
            base_stock = StoreStock.objects.filter(store=profile.store)
        else:
            base_orders = Order.objects.none()
            base_stores = Store.objects.none()
            base_stock = StoreStock.objects.none()

    # === ROW 1: 4 STAT CARDS CHÍNH ===
    total_stores = base_stores.count()
    total_products = Product.objects.count()
    total_orders = base_orders.count()
    total_revenue_dict = base_orders.filter(status='completed').aggregate(total=Sum('total_price'))
    total_revenue = total_revenue_dict['total'] or 0

    # === ROW 2: 4 STAT CARDS PHỤ ===
    pending_orders = base_orders.filter(status='pending').count()
    today = datetime.now().date()
    today_revenue_dict = base_orders.filter(status='completed', created_at__date=today).aggregate(total=Sum('total_price'))
    today_revenue = today_revenue_dict['total'] or 0
    low_stock_count = base_stock.filter(quantity__lt=10, quantity__gt=0).count()

    from django.db.models import Q
    if profile.role == 'super_admin':
        pending_transfers = StockTransfer.objects.filter(status='pending').count()
    elif profile.role == 'regional_manager':
        pending_transfers = StockTransfer.objects.filter(
            Q(from_store__region=profile.region) | Q(to_store__region=profile.region),
            status='pending'
        ).count()
    else:
        if profile.store:
            pending_transfers = StockTransfer.objects.filter(
                Q(from_store=profile.store) | Q(to_store=profile.store),
                status='pending'
            ).count()
        else:
            pending_transfers = 0

    try:
        from apps.core.models import ReturnRequest
        if profile.role == 'super_admin':
            pending_returns = ReturnRequest.objects.filter(status='pending').count()
        elif profile.role == 'regional_manager':
            pending_returns = ReturnRequest.objects.filter(
                order__fulfillment_store__region=profile.region, status='pending'
            ).count()
        else:
            if profile.store:
                pending_returns = ReturnRequest.objects.filter(
                    order__fulfillment_store=profile.store, status='pending'
                ).count()
            else:
                pending_returns = 0
    except ImportError:
        pending_returns = 0

    total_customers = UserProfile.objects.filter(role='customer').count() if profile.role == 'super_admin' else None

    # === BIỂU ĐỒ 7 NGÀY (giữ lại) ===
    seven_days_ago = today - timedelta(days=6)
    revenue_7d = base_orders.filter(
        status='completed', created_at__date__gte=seven_days_ago
    ).annotate(date=TruncDate('created_at')).values('date').annotate(total=Sum('total_price')).order_by('date')

    chart_labels_7d = []
    chart_data_7d = []
    for i in range(7):
        d = seven_days_ago + timedelta(days=i)
        chart_labels_7d.append(d.strftime('%d/%m'))
        daily_total = next((item['total'] for item in revenue_7d if item['date'] == d), 0)
        chart_data_7d.append(float(daily_total))

    # === BIỂU ĐỒ DOANH THU THEO THÁNG ===
    current_year = datetime.now().year
    selected_year = int(request.GET.get('chart_year', current_year))

    # Danh sách năm có đơn hàng
    order_years = base_orders.filter(status='completed').dates('created_at', 'year', order='DESC')
    available_years = sorted(set([d.year for d in order_years] + [current_year]), reverse=True)

    monthly_revenue = base_orders.filter(
        status='completed', created_at__year=selected_year
    ).annotate(month=TruncMonth('created_at')).values('month').annotate(total=Sum('total_price')).order_by('month')

    monthly_labels = []
    monthly_data = []
    for m in range(1, 13):
        monthly_labels.append(f"T{m}")
        monthly_total = next(
            (item['total'] for item in monthly_revenue if item['month'].month == m), 0
        )
        monthly_data.append(float(monthly_total or 0))

    # === PIE CHART: TRẠNG THÁI ĐƠN HÀNG ===
    order_status_counts = [
        base_orders.filter(status='pending').count(),
        base_orders.filter(status='processing').count(),
        base_orders.filter(status='shipped').count(),
        base_orders.filter(status='completed').count(),
        base_orders.filter(status='cancelled').count(),
    ]

    # === ĐƠN HÀNG GẦN ĐÂY (10 đơn) ===
    recent_orders = base_orders.select_related('fulfillment_store').order_by('-created_at')[:10]

    context = {
        # Row 1
        'total_stores': total_stores,
        'total_products': total_products,
        'total_orders': total_orders,
        'total_revenue': total_revenue,
        # Row 2
        'pending_orders': pending_orders,
        'today_revenue': today_revenue,
        'low_stock_count': low_stock_count,
        'pending_transfers': pending_transfers,
        'pending_returns': pending_returns,
        'total_customers': total_customers,
        # Chart 7 ngày
        'chart_labels': chart_labels_7d,
        'chart_data': chart_data_7d,
        # Chart tháng
        'monthly_labels': monthly_labels,
        'monthly_data': monthly_data,
        'available_years': available_years,
        'selected_year': selected_year,
        # Pie chart
        'order_status_counts': order_status_counts,
        # Đơn gần đây
        'recent_orders': recent_orders,
    }
    return render(request, 'admin_custom/dashboard.html', context)


@role_required(['super_admin', 'regional_manager', 'store_admin'])
def export_monthly_revenue_excel(request):
    """Xuất Excel doanh thu theo tháng"""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from django.http import HttpResponse

    profile = request.user.profile
    year = int(request.GET.get('year', datetime.now().year))

    # Data scoping
    if profile.role == 'super_admin':
        base_orders = Order.objects.all()
    elif profile.role == 'regional_manager':
        base_orders = Order.objects.filter(fulfillment_store__region=profile.region)
    else:
        if profile.store:
            base_orders = Order.objects.filter(fulfillment_store=profile.store)
        else:
            base_orders = Order.objects.none()

    wb = Workbook()
    ws = wb.active
    ws.title = f"Doanh thu {year}"

    # Styles
    header_font = Font(bold=True, color="FFFFFF", size=12)
    header_fill = PatternFill(start_color="D70018", end_color="D70018", fill_type="solid")
    col_header_font = Font(bold=True, size=11)
    col_header_fill = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")
    money_fmt = '#,##0'
    thin_border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin')
    )
    total_fill = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")

    # Title row
    ws.merge_cells('A1:F1')
    ws['A1'] = f"BÁO CÁO DOANH THU NĂM {year}"
    ws['A1'].font = header_font
    ws['A1'].fill = header_fill
    ws['A1'].alignment = Alignment(horizontal='center', vertical='center')
    ws.row_dimensions[1].height = 35

    scope_text = "Toàn hệ thống"
    if profile.role == 'regional_manager' and profile.region:
        scope_text = f"Khu vực: {profile.region.name}"
    elif profile.role == 'store_admin' and profile.store:
        scope_text = f"Cửa hàng: {profile.store.name}"
    ws.merge_cells('A2:F2')
    ws['A2'] = f"Phạm vi: {scope_text} | Ngày xuất: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    ws['A2'].font = Font(italic=True, size=10)
    ws['A2'].alignment = Alignment(horizontal='center')

    # Column headers
    columns = ['Tháng', 'Đơn hoàn thành', 'Doanh thu (VNĐ)', 'Đơn bị hủy', 'Tổng đơn hàng', 'Tỷ lệ hoàn thành']
    for col_idx, col_name in enumerate(columns, 1):
        cell = ws.cell(row=4, column=col_idx, value=col_name)
        cell.font = col_header_font
        cell.fill = col_header_fill
        cell.border = thin_border
        cell.alignment = Alignment(horizontal='center')

    # Data rows
    grand_completed = 0
    grand_revenue = 0
    grand_cancelled = 0
    grand_total = 0

    for m in range(1, 13):
        row = 4 + m
        month_orders = base_orders.filter(created_at__year=year, created_at__month=m)
        completed = month_orders.filter(status='completed').count()
        rev = month_orders.filter(status='completed').aggregate(t=Sum('total_price'))['t'] or 0
        cancelled = month_orders.filter(status='cancelled').count()
        total = month_orders.count()
        rate = f"{(completed / total * 100):.1f}%" if total > 0 else "0%"

        grand_completed += completed
        grand_revenue += rev
        grand_cancelled += cancelled
        grand_total += total

        ws.cell(row=row, column=1, value=f"Tháng {m:02d}/{year}").border = thin_border
        ws.cell(row=row, column=2, value=completed).border = thin_border
        ws.cell(row=row, column=2).alignment = Alignment(horizontal='center')
        c = ws.cell(row=row, column=3, value=float(rev))
        c.number_format = money_fmt
        c.border = thin_border
        ws.cell(row=row, column=4, value=cancelled).border = thin_border
        ws.cell(row=row, column=4).alignment = Alignment(horizontal='center')
        ws.cell(row=row, column=5, value=total).border = thin_border
        ws.cell(row=row, column=5).alignment = Alignment(horizontal='center')
        ws.cell(row=row, column=6, value=rate).border = thin_border
        ws.cell(row=row, column=6).alignment = Alignment(horizontal='center')

    # TỔNG CỘNG row
    total_row = 17
    grand_rate = f"{(grand_completed / grand_total * 100):.1f}%" if grand_total > 0 else "0%"
    total_data = ['TỔNG CỘNG', grand_completed, float(grand_revenue), grand_cancelled, grand_total, grand_rate]
    for col_idx, val in enumerate(total_data, 1):
        cell = ws.cell(row=total_row, column=col_idx, value=val)
        cell.font = Font(bold=True, size=11)
        cell.fill = total_fill
        cell.border = thin_border
        if col_idx == 3:
            cell.number_format = money_fmt
        if col_idx in [2, 4, 5, 6]:
            cell.alignment = Alignment(horizontal='center')

    # Column widths
    ws.column_dimensions['A'].width = 18
    ws.column_dimensions['B'].width = 16
    ws.column_dimensions['C'].width = 22
    ws.column_dimensions['D'].width = 14
    ws.column_dimensions['E'].width = 16
    ws.column_dimensions['F'].width = 18

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="Doanh_thu_{year}.xlsx"'
    wb.save(response)
    return response


# =========================================
# 2. QUẢN LÝ KHU VỰC (REGIONS)
# - region_list(): Danh sách khu vực
# - region_add(): Thêm khu vực mới
# - region_edit(): Sửa thông tin khu vực
# - region_delete(): Xóa khu vực
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

# =========================================
# 3. QUẢN LÝ CỬA HÀNG (STORES)
# - store_list(): Danh sách cửa hàng
# - store_add(): Thêm cửa hàng mới
# - store_edit(): Sửa thông tin cửa hàng
# - store_delete(): Xóa cửa hàng
# =========================================
def store_list(request):
    stores = Store.objects.all().order_by('-id')
    return render(request, 'admin_custom/store_list.html', {'stores': stores})

@role_required(['super_admin'])
def store_add(request):
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

    return render(request, 'admin_custom/store_form.html', {'regions': regions})

@role_required(['super_admin'])
def store_edit(request, pk):
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
        if new_image: store.image = new_image
            
        store.save()
        messages.success(request, f"Đã cập nhật chi tiết '{store.name}'!")
        return redirect('client:admin_store_list')

    return render(request, 'admin_custom/store_form.html', {'store': store, 'regions': regions})

@role_required(['super_admin'])
def store_delete(request, pk):
    store = get_object_or_404(Store, pk=pk)
    store_name = store.name
    store.delete()
    messages.warning(request, f"Đã xóa cửa hàng '{store_name}' khỏi hệ thống.")
    return redirect('client:admin_store_list')

# =========================================
# 4. QUẢN LÝ SẢN PHẨM & DANH MỤC
# - product_list(): Danh sách SP (lọc, tìm kiếm, phân trang)
# - product_add(): Thêm SP mới (ảnh, gallery, biến thể)
# - product_edit(): Sửa SP (cập nhật gallery, biến thể)
# - product_delete(): Xóa sản phẩm
# - category_edit(): Sửa danh mục SP
# - category_delete(): Xóa danh mục (chặn nếu còn SP)
# - delete_product_image(): Xóa ảnh phụ trong gallery
# =========================================
@role_required(['super_admin'])
def product_list(request):
    categories = Category.objects.all().order_by('name')
    category_slug = request.GET.get('category')
    search_query = request.GET.get('search')
    price_range = request.GET.get('price_range')
    
    products = Product.objects.all().order_by('-id')
    
    if category_slug: products = products.filter(category__slug=category_slug)
    if search_query:
        if search_query.isdigit(): products = products.filter(id=search_query)
        else: products = products.filter(name__icontains=search_query)
            
    if price_range:
        if price_range == '0-10': products = products.filter(price__lt=10000000)
        elif price_range == '10-20': products = products.filter(price__gte=10000000, price__lte=20000000)
        elif price_range == '20-30': products = products.filter(price__gte=20000000, price__lte=30000000)
        elif price_range == '30+': products = products.filter(price__gt=30000000)

    if request.method == 'POST' and 'add_category' in request.POST:
        cat_name = request.POST.get('cat_name')
        if cat_name:
            new_slug = slugify(cat_name)
            if not Category.objects.filter(slug=new_slug).exists():
                Category.objects.create(name=cat_name, slug=new_slug)
                messages.success(request, f"Đã thêm danh mục: {cat_name}")
                return redirect('client:admin_product_list')
            else:
                messages.error(request, "Danh mục này đã tồn tại.")

    page_obj, preserved_filters = paginate_qs(request, products)
    context = {
        'categories': categories,
        'products': page_obj,
        'page_obj': page_obj,
        'preserved_filters': preserved_filters,
        'selected_category': category_slug,
    }
    return render(request, 'admin_custom/product_management.html', context)

@role_required(['super_admin'])
def product_add(request):
    categories = Category.objects.all()
    if request.method == 'POST':
        name = request.POST.get('name')
        category_id = request.POST.get('category')
        price = request.POST.get('price')
        description = request.POST.get('description')
        content = request.POST.get('content')
        image = request.FILES.get('image')
        
        category = get_object_or_404(Category, id=category_id)
        
        product = Product.objects.create(
            name=name, category=category, price=price,
            description=description, content=content, image=image
        )

        extra_images = request.FILES.getlist('more_images') 
        for img in extra_images:
            ProductImage.objects.create(product=product, image=img)
            
        colors = request.POST.getlist('var_color[]')
        storages = request.POST.getlist('var_storage[]')
        add_prices = request.POST.getlist('var_price[]')
        from apps.core.models import ProductVariation
        for i in range(len(colors)):
            color = colors[i].strip()
            storage = storages[i].strip()
            if color or storage:
                pr = add_prices[i] if i < len(add_prices) and add_prices[i] else 0
                ProductVariation.objects.create(product=product, color=color, storage=storage, additional_price=pr)

        messages.success(request, f"Đã thêm sản phẩm {name} thành công!")
        return redirect('client:admin_product_list')
        
    return render(request, 'admin_custom/product_form.html', {'categories': categories})

@role_required(['super_admin'])
def product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk)
    categories = Category.objects.all()
    
    if request.method == 'POST':
        product.name = request.POST.get('name')
        category_id = request.POST.get('category')
        product.category = get_object_or_404(Category, id=category_id)
        product.price = request.POST.get('price')
        product.description = request.POST.get('description')
        product.content = request.POST.get('content')
        
        new_image = request.FILES.get('image')
        if new_image: product.image = new_image
        
        product.save()

        images_to_delete = request.POST.getlist('delete_images')
        if images_to_delete:
            ProductImage.objects.filter(id__in=images_to_delete).delete()

        extra_images = request.FILES.getlist('more_images')
        for img in extra_images:
            ProductImage.objects.create(product=product, image=img)
            
        var_ids = request.POST.getlist('var_id[]')
        colors = request.POST.getlist('var_color[]')
        storages = request.POST.getlist('var_storage[]')
        add_prices = request.POST.getlist('var_price[]')
        from apps.core.models import ProductVariation
        
        valid_ids = []
        for i in range(len(colors)):
            color = colors[i].strip()
            storage = storages[i].strip()
            if color or storage:
                pr = add_prices[i] if i < len(add_prices) and add_prices[i] else 0
                vid = var_ids[i] if i < len(var_ids) and var_ids[i] else None
                if vid:
                    v = ProductVariation.objects.filter(id=vid, product=product).first()
                    if v:
                        v.color = color; v.storage = storage; v.additional_price = pr; v.save()
                        valid_ids.append(v.id)
                else:
                    v = ProductVariation.objects.create(product=product, color=color, storage=storage, additional_price=pr)
                    valid_ids.append(v.id)
        
        # Xóa các biến thể đã bị gỡ bỏ khỏi form (Trừ khi nó đang bị dính tới kho, có thể gặp lỗi Foreign Key)
        try:
            ProductVariation.objects.filter(product=product).exclude(id__in=valid_ids).delete()
        except: pass

        messages.success(request, f"Cập nhật sản phẩm '{product.name}' thành công!")
        return redirect('client:admin_product_list')
        
    return render(request, 'admin_custom/product_form.html', {
        'product': product, 'categories': categories
    })

@role_required(['super_admin'])
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    product.delete()
    messages.warning(request, "Đã xóa sản phẩm!")
    return redirect('client:admin_product_list')

@role_required(['super_admin'])
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

@role_required(['super_admin'])
def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if category.products.exists():
        messages.error(request, f"Không thể xóa '{category.name}' vì vẫn còn sản phẩm thuộc danh mục này!")
    else:
        category.delete()
        messages.warning(request, f"Đã xóa danh mục '{category.name}' thành công.")
    return redirect('client:admin_product_list')

@role_required(['super_admin'])
def delete_product_image(request, img_id):
    image = get_object_or_404(ProductImage, id=img_id)
    product_id = image.product.id
    image.delete()
    messages.success(request, "Đã xóa ảnh khỏi bộ sưu tập.")
    return redirect('client:admin_product_edit', pk=product_id)

# =========================================
# 5. QUẢN LÝ ĐƠN HÀNG (ORDERS)
# - order_list(): Danh sách đơn hàng (lọc mã, trạng thái, ngày, giá)
# - order_detail(): Chi tiết đơn + kiểm kho + email/notification
# - print_invoice_view(): In hóa đơn
# =========================================
@role_required(['super_admin', 'regional_manager', 'store_admin', 'sales_staff', 'warehouse_keeper'])
def order_list(request):
    profile = request.user.profile
    if profile.role == 'super_admin':
        orders = Order.objects.all().order_by('-created_at')
    elif profile.role == 'regional_manager':
        orders = Order.objects.filter(fulfillment_store__region=profile.region).order_by('-created_at')
    else:
        if profile.store:
            orders = Order.objects.filter(fulfillment_store=profile.store).order_by('-created_at')
        else:
            orders = Order.objects.none()
    
    order_id = request.GET.get('order_id')
    status = request.GET.get('status')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')

    if order_id and order_id.isdigit(): orders = orders.filter(id=order_id)
    if status: orders = orders.filter(status=status)
    if start_date:
        try: orders = orders.filter(created_at__date__gte=datetime.strptime(start_date, '%Y-%m-%d').date())
        except ValueError: pass
    if end_date:
        try: orders = orders.filter(created_at__date__lte=datetime.strptime(end_date, '%Y-%m-%d').date())
        except ValueError: pass
    if min_price and min_price.isdigit(): orders = orders.filter(total_price__gte=int(min_price))
    if max_price and max_price.isdigit(): orders = orders.filter(total_price__lte=int(max_price))

    page_obj, preserved_filters = paginate_qs(request, orders)
    return render(request, 'admin_custom/order_list.html', {
        'orders': page_obj,
        'page_obj': page_obj,
        'preserved_filters': preserved_filters,
    })

@role_required(['super_admin', 'regional_manager', 'store_admin', 'sales_staff', 'warehouse_keeper'])
def order_detail(request, pk):
    order = get_object_or_404(Order, pk=pk)
    
    profile = request.user.profile
    if profile.role != 'super_admin' and order.fulfillment_store != profile.store:
        messages.error(request, 'Bạn không có quyền truy cập đơn hàng của hệ thống khác.')
        return redirect('client:admin_order_list')
        
    order_items = order.items.all() 

    # ----- 1. KIỂM TRA SỐ LƯỢNG TỒN KHO CỦA KHO PHỤ TRÁCH -----
    fulfillment_store = order.fulfillment_store
    is_stock_sufficient = True
    insufficient_items = []
    
    if not order.is_stock_deducted:
        if not fulfillment_store:
            is_stock_sufficient = False
            insufficient_items.append("Chưa gán Cửa hàng phụ trách xuất kho")
        else:
            for item in order_items:
                stock_record = StoreStock.objects.filter(store=fulfillment_store, product=item.product, variation=item.variation).first()
                available_qty = stock_record.quantity if stock_record else 0
                if available_qty < item.quantity:
                    is_stock_sufficient = False
                    opts = f" ({item.color_chosen|default:''} {item.storage_chosen|default:''})".strip() if item.color_chosen or item.storage_chosen else ""
                    insufficient_items.append(f"{item.product.name}{opts}")
    
    # ----- 2. TÌM CHI NHÁNH THAY THẾ (Nếu Kho Chính thiếu hàng) -----
    eligible_alternative_stores = []
    if not is_stock_sufficient and not order.is_stock_deducted:
        all_stores = Store.objects.exclude(id=fulfillment_store.id) if fulfillment_store else Store.objects.all()
        for store in all_stores:
            store_is_eligible = True
            for item in order_items:
                stock_record = StoreStock.objects.filter(store=store, product=item.product, variation=item.variation).first()
                if not stock_record or stock_record.quantity < item.quantity:
                    store_is_eligible = False
                    break
            if store_is_eligible:
                eligible_alternative_stores.append(store)

    # ----- 3. XỬ LÝ CẬP NHẬT ĐƠN -----
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'confirm_payment':
            if order.payment_status != 'paid':
                order.payment_status = 'paid'
                order.save()
                messages.success(request, f"Đã xác nhận thanh toán thành công cho đơn hàng #{order.id}.")
            return redirect('client:admin_order_detail', pk=order.id)
            
        new_status = request.POST.get('status')
        alternative_store_id = request.POST.get('alternative_store_id')
        
        # Nếu chọn chuyển trạng thái thành Hoàn thành (Duyệt Đơn)
        if new_status == 'completed' and not order.is_stock_deducted:
            
            # Nếu User có chọn Kho thay thế -> Gán lại Store cho Order trước
            if alternative_store_id:
                new_store = get_object_or_404(Store, id=alternative_store_id)
                order.fulfillment_store = new_store
                order.save()
                is_stock_sufficient = True # Xóa cờ lỗi
                
            elif not is_stock_sufficient:
                # Nếu Kho hiện tại đang thiếu mà Admin không chọn Kho khác thay thế -> Báo lỗi chặn
                store_name = fulfillment_store.name if fulfillment_store else "Hệ thống"
                error_msg = f"Kho '{store_name}' KHÔNG ĐỦ HÀNG cho: " + ", ".join(insufficient_items)
                messages.error(request, error_msg)
                return redirect('client:admin_order_detail', pk=order.id)

        # Cập nhật trạng thái
        if new_status in dict(Order.STATUS_CHOICES):
            old_status = order.status
            order.status = new_status
            order.save()

            # ==================================================
            # TẠO THÔNG BÁO & GẬI EMAIL KHI ĐỔI TRẠNG THÁI
            # ==================================================
            notif_map = {
                'shipped': {
                    'type': 'order_shipped',
                    'msg': f'Đơn hàng #{order.id} đang trên đường giao đến bạn! Hãy chuẩn bị để nhận hàng nhé.',
                    'template': 'client/emails/order_shipped_email.html',
                    'subject': f'🚚 Đơn hàng #{order.id} đang được giao đến bạn | Phone Store',
                },
                'completed': {
                    'type': 'order_completed',
                    'msg': f'Đơn hàng #{order.id} đã hoàn thành! Cảm ơn bạn đã mua hàng tại Phone Store.',
                    'template': 'client/emails/order_completed_email.html',
                    'subject': f'⭐ Đơn hàng #{order.id} đã hoàn thành | Phone Store',
                },
            }

            if new_status in notif_map and old_status != new_status and order.user:
                info = notif_map[new_status]
                Notification.objects.create(
                    user=order.user,
                    notif_type=info['type'],
                    order=order,
                    message=info['msg'],
                )
                # Gửi email
                try:
                    items_data = [
                        {
                            'name': item.product.name,
                            'quantity': item.quantity,
                            'price': item.price,
                            'subtotal': item.price * item.quantity,
                        }
                        for item in order.items.all()
                    ]
                    html_content = render_to_string(info['template'], {
                        'order': order,
                        'items': items_data,
                        'username': order.user.username,
                    })
                    send_mail(
                        subject=info['subject'],
                        message=strip_tags(html_content),
                        from_email=django_settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[order.user.email],
                        html_message=html_content,
                        fail_silently=True,
                    )
                except Exception:
                    pass

            messages.success(request, f"Đã cập nhật trạng thái đơn hàng #{order.id} thành công!")
            return redirect('client:admin_order_detail', pk=order.id)
    
    context = {
        'order': order, 
        'order_items': order_items, 
        'status_choices': Order.STATUS_CHOICES,
        'is_stock_sufficient': is_stock_sufficient,
        'insufficient_items': insufficient_items,
        'eligible_alternative_stores': eligible_alternative_stores,
    }
    return render(request, 'admin_custom/order_detail.html', context)

@role_required(['super_admin', 'regional_manager', 'store_admin', 'sales_staff', 'warehouse_keeper'])
def print_invoice_view(request, pk):
    order = get_object_or_404(Order, pk=pk)
    
    if order.payment_status != 'paid' and order.payment_method != 'cod':
        messages.warning(request, "Không thể in hóa đơn cho đơn hàng chưa thanh toán thành công!")
        return redirect('client:admin_order_detail', pk=order.id)
        
    order_items = order.items.all()
    
    context = {
        'order': order,
        'order_items': order_items,
        'store': order.fulfillment_store
    }
    return render(request, 'admin_custom/print_invoice.html', context)

# =========================================
# 6. QUẢN LÝ KHO HÀNG (ĐA CHI NHÁNH)
# - admin_stock_management(): Tổng quan tồn kho (lọc, phân quyền)
# - stock_transaction_create(): Tạo phiếu nhập/xuất kho (batch)
# - print_stock_transaction(): In phiếu giao dịch kho
# - store_detail(): Chi tiết cửa hàng + tồn kho
# =========================================
@role_required(['super_admin', 'regional_manager', 'store_admin', 'warehouse_keeper', 'sales_staff'])
def admin_stock_management(request):
    profile = request.user.profile
    categories = Category.objects.all()

    # --- HIỂN THỊ KHO TÙY ROLE (GET ONLY) ---
    category_id = request.GET.get('category')
    stock_status = request.GET.get('stock_status')
    store_filter = request.GET.get('store')
    region_filter = request.GET.get('region')
    stock_data = []

    regions = Region.objects.all()

    # Phân quyền hiển thị (Data Scoping)
    if profile.role == 'super_admin':
        qs = StoreStock.objects.all().select_related('product', 'variation', 'store', 'store__region')
        transactions = StockTransaction.objects.all().select_related('product', 'variation', 'user', 'store_destination').order_by('-created_at')[:30]
        stores = Store.objects.all()
    elif profile.role == 'regional_manager':
        qs = StoreStock.objects.filter(store__region=profile.region).select_related('product', 'variation', 'store', 'store__region')
        transactions = StockTransaction.objects.filter(store_destination__region=profile.region).select_related('product', 'variation', 'user', 'store_destination').order_by('-created_at')[:30]
        stores = Store.objects.filter(region=profile.region)
    else:
        # store_admin, warehouse_keeper, sales_staff
        qs = StoreStock.objects.filter(store=profile.store).select_related('product', 'variation', 'store', 'store__region')
        transactions = StockTransaction.objects.filter(store_destination=profile.store).select_related('product', 'variation', 'user', 'store_destination').order_by('-created_at')[:30]
        stores = Store.objects.filter(id=profile.store_id) if profile.store else Store.objects.none()

    # Áp dụng bộ lọc
    if category_id: qs = qs.filter(product__category_id=category_id)
    if stock_status == 'in_stock': qs = qs.filter(quantity__gt=0)
    elif stock_status == 'out_of_stock': qs = qs.filter(quantity__lte=0)
    elif stock_status == 'low_stock': qs = qs.filter(quantity__gt=0, quantity__lt=10)
    
    if store_filter and profile.role in ['super_admin', 'regional_manager']:
        qs = qs.filter(store_id=store_filter)
    if region_filter and profile.role == 'super_admin':
        qs = qs.filter(store__region_id=region_filter)

    for p in qs:
        stock_data.append({
            'product': p.product, 
            'variation': p.variation, 
            'stock': p.quantity, 
            'reserved': p.reserved_quantity,
            'available': p.available_quantity,
            'store_name': p.store.name if p.store else "Kho Tổng",
            'store_obj': p.store,
        })
        
    # Kho hàng lỗi - Data scoping theo role
    try:
        from apps.core.models import DefectiveProductStock
        if profile.role == 'super_admin':
            defective_stock_data = DefectiveProductStock.objects.select_related('product', 'variation', 'store').all()
        elif profile.role == 'regional_manager':
            defective_stock_data = DefectiveProductStock.objects.filter(store__region=profile.region).select_related('product', 'variation', 'store')
        elif profile.role in ['warehouse_keeper', 'store_admin']:
            defective_stock_data = DefectiveProductStock.objects.filter(store=profile.store).select_related('product', 'variation', 'store')
        else:
            defective_stock_data = []
    except ImportError:
        defective_stock_data = []

    page_obj, preserved_filters = paginate_qs(request, stock_data, per_page=20)

    return render(request, "admin_custom/stock_management.html", {
        "stock_data": page_obj, "categories": categories,
        "transactions": transactions, "stores": stores,
        "regions": regions,
        "defective_stock_data": defective_stock_data,
        "page_obj": page_obj,
        "preserved_filters": preserved_filters,
        "total_stock_count": len(stock_data),
    })

@role_required(['super_admin', 'regional_manager', 'store_admin', 'warehouse_keeper'])
def stock_transaction_create(request, t_type):
    """Tạo phiếu nhập/xuất kho nhiều sản phẩm cùng lúc"""
    profile = request.user.profile
    from apps.core.models import ProductVariation

    if t_type not in ['in', 'out']:
        messages.error(request, "Loại giao dịch không hợp lệ.")
        return redirect('client:admin_stock_management')

    # Lấy danh sách stores theo role
    if profile.role == 'super_admin':
        stores = Store.objects.all().select_related('region')
    elif profile.role == 'regional_manager':
        stores = Store.objects.filter(region=profile.region).select_related('region')
    else:
        stores = Store.objects.filter(id=profile.store_id) if profile.store else Store.objects.none()
    
    products = Product.objects.all().select_related('category').prefetch_related('variations').order_by('name')

    if request.method == 'POST':
        store_id = request.POST.get('store_id')
        note = request.POST.get('note', '')
        row_indices = request.POST.get('row_indices', '').split(',')

        if not store_id:
            messages.error(request, "Vui lòng chọn cửa hàng / kho!")
            return render(request, 'admin_custom/stock_transaction_form.html', {
                'transaction_type': t_type, 'stores': stores, 'products': products,
                'form_title': 'Phiếu Nhập Kho' if t_type == 'in' else 'Phiếu Xuất Kho'
            })

        target_store = get_object_or_404(Store, id=store_id)
        success_count = 0
        errors = []

        with transaction.atomic():
            for idx in row_indices:
                idx = idx.strip()
                if not idx:
                    continue
                    
                product_id = request.POST.get(f'product_id_{idx}')
                variation_id = request.POST.get(f'variation_id_{idx}')
                quantity_str = request.POST.get(f'quantity_{idx}')
                import_price = request.POST.get(f'price_{idx}', '0')

                if not product_id or not quantity_str:
                    continue

                try:
                    quantity = int(quantity_str)
                    if quantity <= 0:
                        continue

                    product = Product.objects.get(id=product_id)
                    variation = ProductVariation.objects.filter(id=variation_id).first() if variation_id else None

                    store_stock, _ = StoreStock.objects.get_or_create(
                        store=target_store, product=product, variation=variation,
                        defaults={'quantity': 0}
                    )

                    if t_type == 'in':
                        store_stock.quantity += quantity
                    elif t_type == 'out':
                        if store_stock.quantity < quantity:
                            errors.append(f"{product.name}: Không đủ hàng (Còn: {store_stock.quantity}, Yêu cầu: {quantity})")
                            continue
                        store_stock.quantity -= quantity
                    
                    store_stock.save()

                    # Ghi Log giao dịch
                    StockTransaction.objects.create(
                        product=product, variation=variation, quantity=quantity,
                        transaction_type=t_type, note=note, user=request.user,
                        price=float(import_price) if import_price and t_type == 'in' else 0,
                        store_destination=target_store
                    )
                    success_count += 1
                except Product.DoesNotExist:
                    errors.append(f"Sản phẩm ID #{product_id} không tồn tại.")
                except Exception as e:
                    errors.append(f"Lỗi dòng {idx}: {str(e)}")

        if success_count > 0:
            action_text = "nhập" if t_type == "in" else "xuất"
            messages.success(request, f"Đã {action_text} thành công {success_count} sản phẩm vào kho [{target_store.name}].")
        for err in errors:
            messages.error(request, err)
        
        return redirect('client:admin_stock_management')

    return render(request, 'admin_custom/stock_transaction_form.html', {
        'transaction_type': t_type,
        'stores': stores,
        'products': products,
        'form_title': 'Phiếu Nhập Kho' if t_type == 'in' else 'Phiếu Xuất Kho'
    })


def print_stock_transaction(request, transaction_id):
    transaction = get_object_or_404(StockTransaction, id=transaction_id)
    return render(request, 'admin_custom/print_stock.html', {'t': transaction})

@role_required(['super_admin', 'regional_manager', 'store_admin'])
def store_detail(request, store_id):
    store = get_object_or_404(Store, id=store_id)
    
    # Lấy dữ liệu từ bảng StoreStock (Trả về dạng Object)
    # Chúng ta xóa .values() để template dùng được item.product.name
    inventory = StoreStock.objects.filter(
        store=store
    ).select_related('product').order_by('-quantity')

    return render(request, 'admin_custom/store_detail.html', {
        'store': store, 
        'inventory': inventory,
        'is_warehouse': store.is_warehouse
    })

# =========================================
# 7. QUẢN LÝ ĐIỀU CHUYỂN KHO
# - transfer_list(): Danh sách phiếu điều chuyển
# - transfer_create(): Tạo phiếu điều chuyển mới
# - transfer_detail(): Chi tiết phiếu điều chuyển
# - transfer_action(): Duyệt xuất / Nhận hàng
# =========================================
@role_required(['super_admin', 'regional_manager', 'store_admin', 'warehouse_keeper', 'sales_staff'])
def transfer_list(request):
    profile = request.user.profile
    if profile.role == 'super_admin':
        transfers = StockTransfer.objects.all()
    elif profile.role == 'regional_manager':
        from django.db.models import Q
        transfers = StockTransfer.objects.filter(Q(from_store__region=profile.region) | Q(to_store__region=profile.region))
    else:
        from django.db.models import Q
        transfers = StockTransfer.objects.filter(Q(from_store=profile.store) | Q(to_store=profile.store))
    transfers = transfers.select_related('from_store', 'to_store', 'created_by').order_by('-created_at')
    page_obj, preserved_filters = paginate_qs(request, transfers)
    return render(request, 'admin_custom/transfer_list.html', {
        'transfers': page_obj,
        'page_obj': page_obj,
        'preserved_filters': preserved_filters,
    })

@role_required(['super_admin', 'regional_manager', 'store_admin', 'warehouse_keeper'])
def transfer_create(request):
    profile = request.user.profile
    if request.method == 'POST':
        to_store_id = request.POST.get('to_store')
        note = request.POST.get('note')
        product_ids = request.POST.getlist('product_id[]')
        quantities = request.POST.getlist('quantity[]')
        
        from_store = profile.store if profile.role != 'super_admin' else get_object_or_404(Store, id=request.POST.get('from_store'))
        to_store = get_object_or_404(Store, id=to_store_id)
        
        # Tạo mã ngẫu nhiên
        import uuid
        code = f"TF-{uuid.uuid4().hex[:6].upper()}"
        
        transfer = StockTransfer.objects.create(
            code=code, from_store=from_store, to_store=to_store, note=note, created_by=request.user
        )
        
        for pid, qty in zip(product_ids, quantities):
            if int(qty) > 0:
                StockTransferItem.objects.create(
                    transfer=transfer, product_id=pid, quantity=int(qty)
                )
        messages.success(request, f"Đã tạo phiếu điều chuyển {code}.")
        return redirect('client:admin_transfer_list')
        
    stores = Store.objects.all()
    products = Product.objects.all()
    return render(request, 'admin_custom/transfer_form.html', {'stores': stores, 'products': products, 'profile': profile})

@role_required(['super_admin', 'regional_manager', 'store_admin', 'warehouse_keeper', 'sales_staff'])
def transfer_detail(request, pk):
    transfer = get_object_or_404(StockTransfer, pk=pk)
    return render(request, 'admin_custom/transfer_detail.html', {'transfer': transfer})

@role_required(['super_admin', 'regional_manager', 'store_admin', 'warehouse_keeper'])
def transfer_action(request, pk):
    transfer = get_object_or_404(StockTransfer, pk=pk)
    action = request.POST.get('action')
    profile = request.user.profile
    
    if action == 'approve': # Duyệt xuất
        if profile.role == 'staff':
            messages.error(request, "Nhân viên không có quyền duyệt xuất kho.")
            return redirect('client:admin_transfer_detail', pk=pk)
            
        # Allow super_admin or regional_manager (if store in region) or store_admin (if store matches)
        has_perm = False
        if profile.role == 'super_admin': has_perm = True
        elif profile.role == 'regional_manager' and transfer.from_store.region == profile.region: has_perm = True
        elif profile.role in ['store_admin', 'warehouse_keeper'] and transfer.from_store == profile.store: has_perm = True
        
        if not has_perm:
            messages.error(request, "Bạn không có quyền duyệt phiếu xuất từ kho này.")
            return redirect('client:admin_transfer_detail', pk=pk)
            
        with transaction.atomic():
            for item in transfer.items.all():
                stock = StoreStock.objects.filter(store=transfer.from_store, product=item.product, variation=item.variation).first()
                if not stock or stock.available_quantity < item.quantity:
                    messages.error(request, f"Kho {transfer.from_store.name} không đủ hàng cho sản phẩm {item.product.name}.")
                    return redirect('client:admin_transfer_detail', pk=pk)
                stock.quantity -= item.quantity
                stock.save()
                StockTransaction.objects.create(
                    product=item.product, variation=item.variation, quantity=item.quantity,
                    transaction_type='transfer_out', store_destination=transfer.to_store,
                    note=f"Xuất điều chuyển {transfer.code}", user=request.user
                )
            transfer.status = 'shipping'
            transfer.shipped_at = timezone.now()
            transfer.approved_by = request.user
            transfer.save()
            messages.success(request, f"Đã xuất kho phiếu {transfer.code}. Đang vận chuyển.")
            
    elif action == 'receive': # Nhận hàng
        has_perm = False
        if profile.role == 'super_admin': has_perm = True
        elif profile.role == 'regional_manager' and transfer.to_store.region == profile.region: has_perm = True
        elif profile.role in ['store_admin', 'warehouse_keeper'] and transfer.to_store == profile.store: has_perm = True
        
        if not has_perm:
            messages.error(request, "Bạn không có quyền nhận phiếu cho kho này.")
            return redirect('client:admin_transfer_detail', pk=pk)
            
        with transaction.atomic():
            for item in transfer.items.all():
                stock, _ = StoreStock.objects.get_or_create(
                    store=transfer.to_store, product=item.product, variation=item.variation, defaults={'quantity':0}
                )
                stock.quantity += item.quantity
                stock.save()
                StockTransaction.objects.create(
                    product=item.product, variation=item.variation, quantity=item.quantity,
                    transaction_type='transfer_in', store_destination=transfer.to_store,
                    note=f"Nhận điều chuyển {transfer.code}", user=request.user
                )
            transfer.status = 'completed'
            transfer.completed_at = timezone.now()
            transfer.received_by = request.user
            transfer.save()
            messages.success(request, f"Đã nhận hàng phiếu {transfer.code}.")

    return redirect('client:admin_transfer_detail', pk=pk)

# =========================================
# 8. QUẢN LÝ PHIẾU KIỂM KÊ
# - stocktaking_list(): Danh sách phiếu kiểm kê
# - stocktaking_create(): Tạo phiếu kiểm kê mới
# - stocktaking_detail(): Chi tiết phiếu kiểm kê
# - stocktaking_action(): Duyệt phiếu + cân bằng kho tự động
# =========================================

@role_required(['super_admin', 'regional_manager', 'store_admin', 'warehouse_keeper', 'sales_staff'])
def stocktaking_list(request):
    profile = request.user.profile

    if profile.role == 'super_admin':
        stocktakings = Stocktaking.objects.all().select_related('store', 'created_by').order_by('-created_at')
    elif profile.role == 'regional_manager':
        stocktakings = Stocktaking.objects.filter(store__region=profile.region).select_related('store', 'created_by').order_by('-created_at')
    else:
        stocktakings = Stocktaking.objects.filter(store=profile.store).select_related('store', 'created_by').order_by('-created_at')
        
    page_obj, preserved_filters = paginate_qs(request, stocktakings)
    return render(request, 'admin_custom/stocktaking_list.html', {
        'stocktakings': page_obj,
        'page_obj': page_obj,
        'preserved_filters': preserved_filters,
        'profile': profile,
    })

@role_required(['super_admin', 'regional_manager', 'store_admin', 'warehouse_keeper'])
def stocktaking_create(request):
    profile = request.user.profile
    
    if request.method == "POST":
        store_id = request.POST.get('store_id')
        note = request.POST.get('note', '')
        
        store = Store.objects.get(id=store_id)
        
        # Tạo mã phiếu
        import uuid
        code = f"KK-{str(uuid.uuid4())[:8].upper()}"
        
        with transaction.atomic():
            stocktaking = Stocktaking.objects.create(
                code=code, store=store, note=note, created_by=request.user
            )
            
            # Lặp qua tất cả input POST dạng: `actual_quantity_{product_id}_{variation_id}`
            for key, value in request.POST.items():
                if key.startswith('actual_quantity_'):
                    parts = key.split('_')
                    product_id = parts[2]
                    variation_id = parts[3] if len(parts) > 3 and parts[3] else None
                    
                    product = Product.objects.get(id=product_id)
                    variation = ProductVariation.objects.get(id=variation_id) if variation_id else None
                    
                    # Lấy system_quantity
                    stock_record = StoreStock.objects.filter(store=store, product=product, variation=variation).first()
                    system_qty = stock_record.quantity if stock_record else 0
                    
                    actual_qty = int(value)
                    
                    # Tạo item
                    StocktakingItem.objects.create(
                        stocktaking=stocktaking, product=product, variation=variation,
                        system_quantity=system_qty, actual_quantity=actual_qty
                    )
            messages.success(request, f"Tạo Phiếu Kiểm Kê {code} thành công!")
            return redirect('client:admin_stocktaking_detail', pk=stocktaking.id)
            
    # GET
    stores = Store.objects.all() if profile.role == 'super_admin' else [profile.store]
    
    # Load sẵn tồn kho của chi nhánh được chọn (hoặc chi nhánh đầu tiên)
    store_id = request.GET.get('store_id')
    if store_id:
        selected_store = Store.objects.filter(id=store_id).first()
    else:
        selected_store = stores[0] if stores else None
        
    current_inventory = StoreStock.objects.filter(store=selected_store).select_related('product', 'variation') if selected_store else []
    
    return render(request, 'admin_custom/stocktaking_form.html', {
        'stores': stores, 'current_inventory': current_inventory, 'profile': profile
    })

@role_required(['super_admin', 'regional_manager', 'store_admin', 'warehouse_keeper', 'sales_staff'])
def stocktaking_detail(request, pk):
    stocktaking = get_object_or_404(Stocktaking, pk=pk)
    return render(request, 'admin_custom/stocktaking_detail.html', {'stocktaking': stocktaking})

@role_required(['super_admin', 'regional_manager', 'store_admin'])
def stocktaking_action(request, pk):
    stocktaking = get_object_or_404(Stocktaking, pk=pk)
    action = request.POST.get('action')
    profile = request.user.profile
    
    if action == 'approve':
        if stocktaking.status != 'draft':
            messages.error(request, "Phiếu này đã được xử lý.")
            return redirect('client:admin_stocktaking_detail', pk=pk)
            
        has_perm = False
        if profile.role == 'super_admin': has_perm = True
        elif profile.role == 'regional_manager' and stocktaking.store.region == profile.region: has_perm = True
        elif profile.role in ['store_admin', 'warehouse_keeper'] and stocktaking.store == profile.store: has_perm = True
        
        if not has_perm:
            messages.error(request, "Bạn không có quyền duyệt phiếu kiểm kê này.")
            return redirect('client:admin_stocktaking_detail', pk=pk)
            
        with transaction.atomic():
            for item in stocktaking.items.all():
                if item.discrepancy != 0:
                    stock_record, _ = StoreStock.objects.get_or_create(
                        store=stocktaking.store, product=item.product, variation=item.variation,
                        defaults={'quantity': 0}
                    )
                    
                    if item.discrepancy > 0:
                        # Dư -> Nhập cân bằng
                        StockTransaction.objects.create(
                            product=item.product, variation=item.variation, quantity=item.discrepancy,
                            transaction_type='inventory_gain', note=f"Cân bằng kho (Dư) - Phiếu {stocktaking.code}",
                            user=request.user, store_destination=stocktaking.store
                        )
                    else:
                        # Thiếu -> Xuất cân bằng
                        StockTransaction.objects.create(
                            product=item.product, variation=item.variation, quantity=abs(item.discrepancy),
                            transaction_type='inventory_loss', note=f"Cân bằng kho (Hao hụt) - Phiếu {stocktaking.code}",
                            user=request.user, store_destination=stocktaking.store
                        )
                        
                    # Cập nhật số liệu chuẩn xác
                    stock_record.quantity = item.actual_quantity
                    stock_record.save()
                    
            stocktaking.status = 'approved'
            stocktaking.approved_by = request.user
            stocktaking.save()
            messages.success(request, f"Duyệt Phiếu Kiểm Kê {stocktaking.code} thành công. Đã cập nhật Tồn Kho!")
            
    return redirect('client:admin_stocktaking_detail', pk=pk)

# =========================================
# 9. QUẢN LÝ NHÂN SỰ
# - admin_employee_list(): Danh sách + phân quyền RBAC nhân viên
# =========================================
@role_required(['super_admin', 'regional_manager', 'store_admin'])
def admin_employee_list(request):
    profile = request.user.profile
    
    # ==== LẤY GET PARAMETERS LỌC ====
    search_query = request.GET.get('search', '').strip()
    role_filter = request.GET.get('role', '')
    store_filter = request.GET.get('store', '')

    if profile.role == 'super_admin':
        employees = UserProfile.objects.exclude(user=request.user).select_related('user', 'store', 'region').order_by('-id')
        stores = Store.objects.all()
    elif profile.role == 'regional_manager':
        employees = UserProfile.objects.filter(
            store__region=profile.region
        ).exclude(user=request.user).select_related('user', 'store', 'region').order_by('-id')
        stores = Store.objects.filter(region=profile.region)
    else:
        employees = UserProfile.objects.filter(
            store=profile.store, 
            role__in=['warehouse_keeper', 'sales_staff']
        ).select_related('user', 'store', 'region').order_by('-id')
        stores = Store.objects.filter(id=profile.store_id)

    # ==== ÁP DỤNG BỘ LỌC ====
    if search_query:
        from django.db.models import Q
        employees = employees.filter(
            Q(user__username__icontains=search_query) | 
            Q(user__email__icontains=search_query) |
            Q(phone__icontains=search_query)
        )
        
    if role_filter:
        employees = employees.filter(role=role_filter)
        
    if profile.role == 'super_admin' and store_filter:
        if store_filter == 'none':
            employees = employees.filter(store__isnull=True)
        else:
            employees = employees.filter(store_id=store_filter)

    regions = Region.objects.all()

    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        new_role = request.POST.get('role')
        store_id = request.POST.get('store_id')
        region_id = request.POST.get('region_id')

        try:
            target_profile = UserProfile.objects.get(user__id=user_id)
            
            # Kiểm tra quyền: QL Cửa hàng chỉ được phân quyền nhân viên cấp dưới
            if profile.role == 'store_admin':
                if target_profile.store != profile.store or new_role in ['super_admin', 'regional_manager', 'store_admin']:
                    messages.error(request, "Bạn không có quyền thực hiện thao tác này!")
                    return redirect('client:admin_employee_list')
            
            # Kiểm tra quyền: QL Vùng chỉ phân quyền trong vùng mình
            if profile.role == 'regional_manager':
                if new_role in ['super_admin', 'regional_manager']:
                    messages.error(request, "Bạn không có quyền gán vai trò này!")
                    return redirect('client:admin_employee_list')

            target_profile.role = new_role
            
            # Xử lý Khu vực
            if new_role == 'regional_manager':
                target_profile.region = Region.objects.filter(id=region_id).first() if region_id else None
                target_profile.store = None  # QL Vùng không thuộc cửa hàng cụ thể
            elif new_role in ['super_admin', 'customer']:
                target_profile.store = None
                target_profile.region = None
            else:
                target_profile.region = None
                if store_id:
                    target_profile.store = get_object_or_404(Store, id=store_id)
                else:
                    target_profile.store = None
                
            target_profile.save()

            target_user = target_profile.user
            target_user.is_staff = new_role in ['super_admin', 'regional_manager', 'store_admin', 'warehouse_keeper', 'sales_staff']
            target_user.is_superuser = (new_role == 'super_admin')
            target_user.save()
            
            messages.success(request, f"Đã cập nhật quyền cho tài khoản '{target_profile.user.username}'!")
        except UserProfile.DoesNotExist:
            messages.error(request, "Không tìm thấy người dùng này trong hệ thống.")
            
        return redirect('client:admin_employee_list')

    page_obj, preserved_filters = paginate_qs(request, employees)
    return render(request, 'admin_custom/employee_management.html', {
        'employees': page_obj, 'stores': stores, 'regions': regions,
        'role_choices': UserProfile.ROLE_CHOICES,
        'page_obj': page_obj,
        'preserved_filters': preserved_filters,
    })

# =========================================
# 10. QUẢN LÝ FLASH SALE
# - admin_flash_sale(): Danh sách + tạo Flash Sale
# - delete_flash_sale(): Xóa Flash Sale
# =========================================
@role_required(['super_admin'])
def admin_flash_sale(request):
    flash_sales = FlashSale.objects.all().select_related('product').order_by('-id')
    available_products = Product.objects.filter(flash_sale__isnull=True)

    if request.method == 'POST':
        product_id = request.POST.get('product_id')
        flash_price = request.POST.get('flash_price')
        end_time = request.POST.get('end_time')

        try:
            product = get_object_or_404(Product, id=product_id)
            FlashSale.objects.create(
                product=product,
                flash_price=flash_price,
                end_time=end_time,
                is_active=True
            )
            messages.success(request, f"Đã thiết lập Flash Sale cho '{product.name}'!")
        except Exception as e:
            messages.error(request, f"Có lỗi xảy ra: {str(e)}")
            
        return redirect('client:admin_flash_sale')

    page_obj, preserved_filters = paginate_qs(request, flash_sales)
    return render(request, 'admin_custom/flash_sale_management.html', {
        'flash_sales': page_obj,
        'available_products': available_products,
        'page_obj': page_obj,
        'preserved_filters': preserved_filters,
    })

@role_required(['super_admin'])
def delete_flash_sale(request, pk):
    fs = get_object_or_404(FlashSale, pk=pk)
    fs.delete()
    messages.warning(request, "Đã gỡ bỏ chương trình Flash Sale của sản phẩm này.")
    return redirect('client:admin_flash_sale')


# =========================================
# 11. QUẢN LÝ MÃ GIẢM GIÁ (COUPON)
# - admin_coupon_list(): Danh sách + tạo mã giảm giá
# - admin_coupon_delete(): Xóa mã giảm giá
# =========================================
@role_required(['super_admin'])
def admin_coupon_list(request):
    coupons = Coupon.objects.all().order_by('-id')
    
    if request.method == 'POST':
        code = request.POST.get('code')
        discount_type = request.POST.get('discount_type')
        discount_value = request.POST.get('discount_value')
        min_purchase = request.POST.get('min_purchase')
        valid_from = request.POST.get('valid_from')
        valid_to = request.POST.get('valid_to')
        usage_limit = request.POST.get('usage_limit')
        
        try:
            Coupon.objects.create(
                code=code.upper(), # Tự động viết hoa mã
                discount_type=discount_type,
                discount_value=discount_value,
                min_purchase=min_purchase,
                valid_from=valid_from,
                valid_to=valid_to,
                usage_limit=usage_limit
            )
            messages.success(request, f"Đã tạo mã giảm giá '{code.upper()}' thành công!")
        except Exception as e:
            messages.error(request, "Lỗi: Mã giảm giá này đã tồn tại hoặc dữ liệu không hợp lệ.")
            
        return redirect('client:admin_coupon_list')
        
    page_obj, preserved_filters = paginate_qs(request, coupons)
    return render(request, 'admin_custom/coupon_management.html', {
        'coupons': page_obj,
        'page_obj': page_obj,
        'preserved_filters': preserved_filters,
    })

@role_required(['super_admin'])
def admin_coupon_delete(request, pk):
    coupon = get_object_or_404(Coupon, pk=pk)
    coupon.delete()
    messages.success(request, "Đã xóa mã giảm giá!")
    return redirect('client:admin_coupon_list')


# =========================================
# 12. NHẬP / XUẤT EXCEL (ADMIN)
# - _excel_styles(): Helper style cho Excel
# - export_products_excel(): Xuất danh sách SP ra Excel
# - import_products_excel(): Import SP từ Excel
# - export_orders_excel(): Xuất danh sách đơn hàng ra Excel
# - download_product_template(): Tải template Excel mẫu
# =========================================
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from django.http import HttpResponse
import datetime as _dt


def _excel_styles():
    """Trả về bộ style dùng chung cho các file Excel."""
    thin = Side(border_style='thin', color='DDDDDD')
    return {
        'red_fill':    PatternFill('solid', fgColor='D70018'),
        'blue_fill':   PatternFill('solid', fgColor='1A3C6E'),
        'gray_fill':   PatternFill('solid', fgColor='F5F5F5'),
        'yel_fill':    PatternFill('solid', fgColor='FFF3CD'),
        'h_font':      Font(name='Calibri', bold=True, color='FFFFFF', size=11),
        'body_font':   Font(name='Calibri', size=10),
        'bold_font':   Font(name='Calibri', bold=True, size=10),
        'center':      Alignment(horizontal='center', vertical='center', wrap_text=True),
        'left':        Alignment(horizontal='left',   vertical='center', wrap_text=True),
        'right':       Alignment(horizontal='right',  vertical='center'),
        'border':      Border(left=thin, right=thin, top=thin, bottom=thin),
    }


@role_required(['super_admin', 'regional_manager', 'store_admin', 'warehouse_keeper', 'sales_staff'])
def export_products_excel(request):
    """Xuất danh sách sản phẩm ra file Excel có định dạng đẹp."""
    s = _excel_styles()
    wb = Workbook()
    ws = wb.active
    ws.title = 'San pham'

    ts = _dt.datetime.now().strftime('%d/%m/%Y %H:%M')
    ws.merge_cells('A1:H1')
    tc = ws['A1']
    tc.value = f'DANH SÁCH SẢN PHẨM – Phone Store  |  Xuất lúc: {ts}'
    tc.font = Font(name='Calibri', bold=True, size=14, color='D70018')
    tc.alignment = s['center']
    ws.row_dimensions[1].height = 30

    headers = ['ID', 'Tên sản phẩm', 'ID Danh mục', 'Tên danh mục', 'Giá bán (VND)', 'Tồn kho', 'Mô tả', 'Slug']
    ws.append(headers)
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=2, column=col_idx)
        cell.fill = s['red_fill']; cell.font = s['h_font']
        cell.alignment = s['center']; cell.border = s['border']
    ws.row_dimensions[2].height = 24

    products = Product.objects.select_related('category').all().order_by('id')
    for row_idx, p in enumerate(products, 3):
        slug     = p.slug if hasattr(p, 'slug') else ''
        row_data = [p.id, p.name,
                    p.category.id   if p.category else '',
                    p.category.name if p.category else '',
                    float(p.price or 0), p.stock or 0, p.description or '', slug]
        ws.append(row_data)
        fill = s['gray_fill'] if row_idx % 2 == 0 else PatternFill('solid', fgColor='FFFFFF')
        for col_idx, _ in enumerate(row_data, 1):
            cell = ws.cell(row=row_idx, column=col_idx)
            cell.fill = fill; cell.border = s['border']
            if col_idx in (1, 3):
                cell.alignment = s['center']; cell.font = s['bold_font']
            elif col_idx == 5:
                cell.alignment = s['right'];  cell.font = s['body_font']
                cell.number_format = '#,##0'
            elif col_idx == 6:
                cell.alignment = s['center']; cell.font = s['body_font']
            else:
                cell.alignment = s['left'];   cell.font = s['body_font']

    for i, w in enumerate([8, 40, 12, 22, 18, 10, 50, 30], 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = 'A3'

    # Sheet 2: Danh muc tham chieu
    ws2 = wb.create_sheet(title='Danh muc')
    ws2.append(['ID Danh mục', 'Tên danh mục'])
    for col_idx in range(1, 3):
        cell = ws2.cell(row=1, column=col_idx)
        cell.fill = s['red_fill']; cell.font = s['h_font']
        cell.alignment = s['center']; cell.border = s['border']
    ws2.column_dimensions['A'].width = 15
    ws2.column_dimensions['B'].width = 30
    for cat in Category.objects.all().order_by('id'):
        ws2.append([cat.id, cat.name])
        for c in [ws2.cell(row=ws2.max_row, column=1), ws2.cell(row=ws2.max_row, column=2)]:
            c.border = s['border']; c.alignment = s['left']

    fname = f'san_pham_{_dt.datetime.now().strftime("%Y%m%d_%H%M")}.xlsx'
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="{fname}"'
    wb.save(response)
    return response


@role_required(['super_admin', 'regional_manager', 'store_admin', 'warehouse_keeper', 'sales_staff'])
def import_products_excel(request):
    """Import sản phẩm từ file Excel với validation đầy đủ và báo cáo lỗi chi tiết."""
    if request.method != 'POST' or not request.FILES.get('excel_file'):
        return redirect(request.META.get('HTTP_REFERER', '/'))

    excel_file = request.FILES['excel_file']
    if not (excel_file.name.endswith('.xlsx') or excel_file.name.endswith('.xls')):
        messages.error(request, 'Vui lòng tải lên file định dạng .xlsx hoặc .xls')
        return redirect(request.META.get('HTTP_REFERER', '/'))

    try:
        wb = load_workbook(excel_file, data_only=True)
        ws = wb.active
        count_created = 0
        count_updated = 0
        errors = []
        valid_cat_ids = set(Category.objects.values_list('id', flat=True))

        for row_num, row in enumerate(ws.iter_rows(min_row=3, values_only=True), start=3):
            if all(cell is None for cell in row):
                continue

            product_id  = row[0] if len(row) > 0 else None
            name        = str(row[1]).strip() if len(row) > 1 and row[1] else ''
            cat_id_raw  = row[2] if len(row) > 2 else None
            price_raw   = row[4] if len(row) > 4 else 0
            stock_raw   = row[5] if len(row) > 5 else 0
            description = str(row[6]).strip() if len(row) > 6 and row[6] else ''

            if not name:
                errors.append(f'Dòng {row_num}: Tên sản phẩm bị trống → bỏ qua.')
                continue
            if cat_id_raw is None or cat_id_raw == '':
                errors.append(f'Dòng {row_num} ({name}): Thiếu ID Danh mục → bỏ qua.')
                continue
            try:
                clean_cat_id = int(float(str(cat_id_raw)))
            except (ValueError, TypeError):
                errors.append(f'Dòng {row_num} ({name}): ID Danh mục "{cat_id_raw}" không hợp lệ → bỏ qua.')
                continue
            if clean_cat_id not in valid_cat_ids:
                errors.append(f'Dòng {row_num} ({name}): Danh mục ID={clean_cat_id} không tồn tại → bỏ qua.')
                continue
            try:
                clean_price = float(str(price_raw).replace(',', '').replace('.', '')) if price_raw not in (None, '') else 0
            except (ValueError, TypeError):
                errors.append(f'Dòng {row_num} ({name}): Giá "{price_raw}" không hợp lệ → đặt về 0.')
                clean_price = 0
            try:
                clean_stock = int(float(str(stock_raw))) if stock_raw not in (None, '') else 0
            except (ValueError, TypeError):
                errors.append(f'Dòng {row_num} ({name}): Tồn kho "{stock_raw}" không hợp lệ → đặt về 0.')
                clean_stock = 0

            if product_id:
                try:
                    prod = Product.objects.get(id=int(float(str(product_id))))
                    old_stock = prod.stock
                    
                    prod.name = name; prod.category_id = clean_cat_id
                    prod.price = clean_price; prod.stock = clean_stock
                    prod.description = description; prod.save()
                    
                    # Ghi log nếu số lượng có thay đổi
                    if clean_stock != old_stock:
                        diff = clean_stock - old_stock
                        from apps.core.models import StockTransaction
                        StockTransaction.objects.create(
                            product=prod,
                            quantity=abs(diff),
                            transaction_type='in' if diff > 0 else 'out',
                            note='Điều chỉnh/Nhập hàng qua hệ thống import Excel',
                            user=request.user
                        )
                        
                    count_updated += 1
                except Product.DoesNotExist:
                    errors.append(f'Dòng {row_num} ({name}): SP ID={product_id} không tồn tại → bỏ qua.')
                except Exception as ex:
                    errors.append(f'Dòng {row_num} ({name}): Lỗi cập nhật – {ex}')
            else:
                try:
                    product = Product.objects.create(name=name, category_id=clean_cat_id,
                                           price=clean_price, stock=clean_stock, description=description)
                    
                    # Ghi log khi tạo mới sản phẩm mà có tồn kho > 0
                    if clean_stock > 0:
                        from apps.core.models import StockTransaction
                        StockTransaction.objects.create(
                            product=product,
                            quantity=clean_stock,
                            transaction_type='in',
                            note='Cơ sở dữ liệu khởi tạo kho lần đầu qua Excel',
                            user=request.user
                        )
                        
                    count_created += 1
                except Exception as ex:
                    errors.append(f'Dòng {row_num} ({name}): Lỗi tạo mới – {ex}')

        if count_created or count_updated:
            messages.success(request,
                f'✅ Import thành công! Thêm mới: {count_created} SP | Cập nhật: {count_updated} SP'
                + (f' | ⚠️ {len(errors)} dòng lỗi' if errors else '.'))
        else:
            messages.warning(request, f'Không có sản phẩm nào được xử lý. {len(errors)} dòng lỗi.')

        for err in errors[:10]:
            messages.warning(request, f'⚠️ {err}')
        if len(errors) > 10:
            messages.info(request, f'... và {len(errors) - 10} lỗi khác không hiển thị.')

    except Exception as e:
        messages.error(request, f'Không thể đọc file Excel: {str(e)}')

    return redirect(request.META.get('HTTP_REFERER', '/'))


@role_required(['super_admin', 'regional_manager', 'store_admin', 'sales_staff'])
def export_orders_excel(request):
    """Xuất danh sách đơn hàng ra file Excel có style."""
    s = _excel_styles()
    orders = Order.objects.select_related('user').order_by('-created_at')
    status = request.GET.get('status')
    if status:
        orders = orders.filter(status=status)

    wb = Workbook()
    ws = wb.active
    ws.title = 'Don hang'

    ts = _dt.datetime.now().strftime('%d/%m/%Y %H:%M')
    ws.merge_cells('A1:J1')
    tc = ws['A1']
    tc.value = f'DANH SÁCH ĐƠN HÀNG – Phone Store  |  Xuất lúc: {ts}'
    tc.font = Font(name='Calibri', bold=True, size=14, color='1A3C6E')
    tc.alignment = s['center']
    ws.row_dimensions[1].height = 30

    STATUS_MAP = {'pending': 'Chờ xử lý', 'processing': 'Đang xử lý',
                  'shipped': 'Đang giao', 'completed': 'Hoàn thành', 'cancelled': 'Đã hủy'}
    headers = ['Mã đơn', 'Khách hàng', 'Email', 'SĐT', 'Địa chỉ giao hàng',
               'Tổng tiền (VND)', 'Giảm giá (VND)', 'Trạng thái', 'PTTT', 'Ngày đặt']
    ws.append(headers)
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=2, column=col_idx)
        cell.fill = s['blue_fill']; cell.font = s['h_font']
        cell.alignment = s['center']; cell.border = s['border']
    ws.row_dimensions[2].height = 22
    ws.freeze_panes = 'A3'

    for row_idx, o in enumerate(orders, 3):
        payment  = o.payment_method if hasattr(o, 'payment_method') and o.payment_method else 'COD'
        row_data = [
            f'#{o.id}',
            o.user.username if o.user else (o.full_name or ''),
            o.user.email    if o.user else '',
            o.phone or '',
            o.address or '',
            float(o.total_price or 0),
            float(o.discount_amount or 0) if hasattr(o, 'discount_amount') else 0,
            STATUS_MAP.get(o.status, o.status),
            payment,
            o.created_at.strftime('%d/%m/%Y %H:%M') if o.created_at else '',
        ]
        ws.append(row_data)
        fill = s['gray_fill'] if row_idx % 2 == 0 else PatternFill('solid', fgColor='FFFFFF')
        for col_idx, _ in enumerate(row_data, 1):
            cell = ws.cell(row=row_idx, column=col_idx)
            cell.fill = fill; cell.border = s['border']; cell.font = s['body_font']
            if col_idx in (6, 7):
                cell.number_format = '#,##0'; cell.alignment = s['right']
            elif col_idx in (1, 8):
                cell.alignment = s['center']
            else:
                cell.alignment = s['left']

    for i, w in enumerate([10, 20, 28, 14, 40, 18, 16, 16, 14, 20], 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    fname = f'don_hang_{_dt.datetime.now().strftime("%Y%m%d_%H%M")}.xlsx'
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="{fname}"'
    wb.save(response)
    return response


@role_required(['super_admin', 'regional_manager', 'store_admin'])
def download_product_template(request):
    """Tạo và tải file Excel template mẫu để hướng dẫn import."""
    s = _excel_styles()
    wb  = Workbook()
    ws  = wb.active
    ws.title = 'San pham (mau)'

    ws.merge_cells('A1:H1')
    t = ws['A1']
    t.value = 'TEMPLATE NHẬP SẢN PHẨM – Phone Store  |  KHÔNG XÓA DÒNG TIÊU ĐỀ'
    t.font  = Font(name='Calibri', bold=True, size=13, color='D70018')
    t.alignment = s['center']
    ws.row_dimensions[1].height = 28

    headers = ['ID', 'Tên sản phẩm (*)', 'ID Danh mục (*)', 'Tên danh mục (tham khảo)',
               'Giá bán (VND) (*)', 'Tồn kho (*)', 'Mô tả', 'Slug (tự động)']
    ws.append(headers)
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=2, column=col_idx)
        cell.fill = s['red_fill']; cell.font = s['h_font']
        cell.alignment = s['center']; cell.border = s['border']
    ws.row_dimensions[2].height = 22

    guide = ['(Để trống = tạo mới)', 'Bắt buộc nhập', 'ID từ sheet Danh muc',
             'Chỉ để tham khảo', '15000000', '10', 'Không bắt buộc', 'Để trống']
    ws.append(guide)
    for col_idx, _ in enumerate(guide, 1):
        cell = ws.cell(row=3, column=col_idx)
        cell.fill = s['yel_fill']
        cell.font = Font(name='Calibri', italic=True, size=9, color='666666')
        cell.alignment = s['center']; cell.border = s['border']

    samples = [
        ['', 'iPhone 15 Pro Max 256GB', 1, 'Điện thoại', 34990000, 5, 'Chip A17 Pro, camera 48MP', ''],
        [1,  'Samsung Galaxy S24 Ultra', 1, 'Điện thoại', 28990000, 3, 'RAM 12GB, Snapdragon 8 Gen 3', ''],
    ]
    for sample in samples:
        ws.append(sample)
        for col_idx in range(1, len(sample) + 1):
            cell = ws.cell(row=ws.max_row, column=col_idx)
            cell.border = s['border']
            cell.alignment = s['center'] if col_idx in (1, 3, 5, 6) else s['left']
            cell.font = Font(name='Calibri', size=10, color='888888', italic=True)

    for i, w in enumerate([8, 40, 15, 25, 18, 10, 50, 20], 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = 'A3'

    ws2 = wb.create_sheet(title='Danh muc')
    ws2.append(['ID Danh muc', 'Ten danh muc'])
    for col_idx in range(1, 3):
        c = ws2.cell(row=1, column=col_idx)
        c.fill = s['red_fill']; c.font = s['h_font']
        c.alignment = s['center']; c.border = s['border']
    ws2.column_dimensions['A'].width = 15
    ws2.column_dimensions['B'].width = 30
    for cat in Category.objects.all().order_by('id'):
        ws2.append([cat.id, cat.name])
        for c in [ws2.cell(row=ws2.max_row, column=1), ws2.cell(row=ws2.max_row, column=2)]:
            c.border = s['border']; c.alignment = s['left']

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="template_san_pham.xlsx"'
    wb.save(response)
    return response


# =========================================
# 13. QUẢN LÝ YÊU CẦU TRẢ HÀNG
# - admin_return_list(): Danh sách yêu cầu trả hàng
# - admin_return_detail(): Chi tiết + duyệt/từ chối/hoàn tất trả hàng
# =========================================
@role_required(['super_admin', 'regional_manager', 'store_admin', 'warehouse_keeper', 'sales_staff'])
def admin_return_list(request):
    try:
        from apps.core.models import ReturnRequest
    except ImportError:
        pass
        
    profile = request.user.profile
    if profile.role == 'super_admin':
        returns = ReturnRequest.objects.all().order_by('-created_at')
    else:
        if profile.store:
            returns = ReturnRequest.objects.filter(order__fulfillment_store=profile.store).order_by('-created_at')
        else:
            returns = ReturnRequest.objects.none()
            
    page_obj, preserved_filters = paginate_qs(request, returns)
    return render(request, 'admin_custom/return_management.html', {
        'returns': page_obj,
        'page_obj': page_obj,
        'preserved_filters': preserved_filters,
    })

@role_required(['super_admin', 'regional_manager', 'store_admin', 'warehouse_keeper', 'sales_staff'])
def admin_return_detail(request, pk):
    try:
        from apps.core.models import ReturnRequest
    except ImportError:
        pass
        
    return_req = get_object_or_404(ReturnRequest, pk=pk)
    profile = request.user.profile
    
    # Check permission
    if profile.role != 'super_admin':
        if not profile.store or return_req.order.fulfillment_store != profile.store:
            messages.error(request, "Bạn không có quyền quản lý yêu cầu trả hàng của chi nhánh khác.")
            return redirect('client:admin_return_list')
            
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'approve':
            return_req.status = 'approved'
            return_req.save()
            messages.success(request, f"Đã phê duyệt yêu cầu #{return_req.id}. Chờ nhận hàng từ khách.")
        elif action == 'reject':
            return_req.status = 'rejected'
            return_req.save()
            messages.warning(request, f"Đã từ chối yêu cầu trả hàng #{return_req.id}.")
        elif action == 'complete':
            return_req.status = 'completed'
            return_req.save()
            messages.success(request, f"Đã hoàn tất trả hàng #{return_req.id}. Hàng lỗi/cũ đã nhập kho, điểm và chi tiêu đã được thu hồi.")
            
        return redirect('client:admin_return_detail', pk=return_req.id)
        
    return render(request, 'admin_custom/return_detail.html', {'return_req': return_req})

# =========================================
# 14. QUẢN LÝ TIN TỨC (NEWS)
# - admin_news_list(): Danh sách bài viết
# - admin_news_create(): Tạo bài viết mới
# - admin_news_edit(): Sửa bài viết
# - admin_news_delete(): Xóa bài viết
# - admin_news_category(): Quản lý danh mục tin tức
# =========================================
@role_required(['super_admin', 'regional_manager', 'store_admin'])
def admin_news_list(request):
    from apps.core.models import NewsArticle, NewsCategory
    from django.core.paginator import Paginator
    
    qs = NewsArticle.objects.all().order_by('-created_at')
    
    q = request.GET.get('q', '')
    cat_id = request.GET.get('category', '')
    if q:
        qs = qs.filter(title__icontains=q)
    if cat_id:
        qs = qs.filter(category_id=cat_id)
        
    paginator = Paginator(qs, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    categories = NewsCategory.objects.all()
    
    context = {
        'page_obj': page_obj,
        'categories': categories,
        'q': q,
        'cat_id': cat_id,
    }
    return render(request, 'admin_custom/news_list.html', context)

@role_required(['super_admin', 'regional_manager', 'store_admin'])
def admin_news_create(request):
    from apps.core.models import NewsArticle, NewsCategory
    categories = NewsCategory.objects.all()
    if request.method == 'POST':
        title = request.POST.get('title')
        category_id = request.POST.get('category')
        short_description = request.POST.get('short_description')
        content = request.POST.get('content')
        is_published = request.POST.get('is_published') == 'on'
        is_pinned = request.POST.get('is_pinned') == 'on'
        
        thumbnail = request.FILES.get('thumbnail')
        
        category = NewsCategory.objects.filter(id=category_id).first() if category_id else None
        
        article = NewsArticle.objects.create(
            title=title,
            category=category,
            short_description=short_description,
            content=content,
            is_published=is_published,
            is_pinned=is_pinned,
            author=request.user
        )
        if thumbnail:
            article.thumbnail = thumbnail
            article.save()
            
        messages.success(request, "Thêm bài viết thành công!")
        return redirect('client:admin_news_list')
        
    return render(request, 'admin_custom/news_form.html', {'categories': categories})

@role_required(['super_admin', 'regional_manager', 'store_admin'])
def admin_news_edit(request, pk):
    from apps.core.models import NewsArticle, NewsCategory
    article = get_object_or_404(NewsArticle, pk=pk)
    categories = NewsCategory.objects.all()
    
    if request.method == 'POST':
        article.title = request.POST.get('title')
        category_id = request.POST.get('category')
        article.category = NewsCategory.objects.filter(id=category_id).first() if category_id else None
        article.short_description = request.POST.get('short_description')
        article.content = request.POST.get('content')
        article.is_published = request.POST.get('is_published') == 'on'
        article.is_pinned = request.POST.get('is_pinned') == 'on'
        
        thumbnail = request.FILES.get('thumbnail')
        if thumbnail:
            article.thumbnail = thumbnail
            
        article.save()
        messages.success(request, "Cập nhật bài viết thành công!")
        return redirect('client:admin_news_list')
        
    return render(request, 'admin_custom/news_form.html', {'article': article, 'categories': categories})

@role_required(['super_admin', 'regional_manager', 'store_admin'])
def admin_news_delete(request, pk):
    from apps.core.models import NewsArticle
    article = get_object_or_404(NewsArticle, pk=pk)
    if request.method == 'POST':
        article.delete()
        messages.success(request, "Đã xóa bài viết.")
    return redirect('client:admin_news_list')

@role_required(['super_admin', 'regional_manager', 'store_admin'])
def admin_news_toggle_pin(request, pk):
    from apps.core.models import NewsArticle
    article = get_object_or_404(NewsArticle, pk=pk)
    if request.method == 'POST':
        article.is_pinned = not article.is_pinned
        article.save()
        status = "ghim" if article.is_pinned else "bỏ ghim"
        messages.success(request, f"Đã {status} bài viết \"{article.title}\".")
    return redirect('client:admin_news_list')

@role_required(['super_admin', 'regional_manager', 'store_admin'])
def admin_news_category(request):
    from apps.core.models import NewsCategory
    categories = NewsCategory.objects.all()
    
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add':
            name = request.POST.get('name')
            if name:
                NewsCategory.objects.create(name=name)
                messages.success(request, "Đã thêm danh mục.")
        elif action == 'edit':
            cat_id = request.POST.get('cat_id')
            name = request.POST.get('name')
            cat = NewsCategory.objects.filter(id=cat_id).first()
            if cat and name:
                cat.name = name
                cat.slug = '' # force regenerate
                cat.save()
                messages.success(request, "Đã cập nhật danh mục.")
        elif action == 'delete':
            cat_id = request.POST.get('cat_id')
            cat = NewsCategory.objects.filter(id=cat_id).first()
            if cat:
                cat.delete()
                messages.success(request, "Đã xóa danh mục.")
        return redirect('client:admin_news_category')
        
    return render(request, 'admin_custom/news_category.html', {'categories': categories})

# ----- QUẢN LÝ SỰ KIỆN (EVENTS) -----
@role_required(['super_admin', 'regional_manager', 'store_admin'])
def admin_event_list(request):
    from apps.core.models import Event, NewsArticle
    events = Event.objects.all().order_by('event_date')
    articles = NewsArticle.objects.filter(is_published=True).order_by('-created_at')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add':
            title = request.POST.get('title')
            event_date = request.POST.get('event_date')
            location = request.POST.get('location')
            description = request.POST.get('description', '')
            article_id = request.POST.get('article_id')
            if title and event_date and location:
                event = Event.objects.create(
                    title=title, event_date=event_date,
                    location=location, description=description
                )
                if article_id:
                    event.article = NewsArticle.objects.filter(id=article_id).first()
                    event.save()
                messages.success(request, "Đã thêm sự kiện.")
        elif action == 'edit':
            event_id = request.POST.get('event_id')
            event = Event.objects.filter(id=event_id).first()
            if event:
                event.title = request.POST.get('title')
                event.event_date = request.POST.get('event_date')
                event.location = request.POST.get('location')
                event.description = request.POST.get('description', '')
                event.is_active = request.POST.get('is_active') == 'on'
                article_id = request.POST.get('article_id')
                event.article = NewsArticle.objects.filter(id=article_id).first() if article_id else None
                event.save()
                messages.success(request, "Đã cập nhật sự kiện.")
        return redirect('client:admin_event_list')
    
    return render(request, 'admin_custom/event_management.html', {
        'events': events,
        'articles': articles,
    })

@role_required(['super_admin', 'regional_manager', 'store_admin'])
def admin_event_delete(request, pk):
    from apps.core.models import Event
    event = get_object_or_404(Event, pk=pk)
    if request.method == 'POST':
        event.delete()
        messages.success(request, "Đã xóa sự kiện.")
    return redirect('client:admin_event_list')

# ----- QUẢN LÝ VIDEO YOUTUBE -----
@role_required(['super_admin', 'regional_manager', 'store_admin'])
def admin_youtube_list(request):
    from apps.core.models import YoutubeVideo
    videos = YoutubeVideo.objects.all()
    
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add':
            title = request.POST.get('title')
            youtube_url = request.POST.get('youtube_url')
            display_order = request.POST.get('display_order', 0)
            if title and youtube_url:
                YoutubeVideo.objects.create(
                    title=title, youtube_url=youtube_url,
                    display_order=int(display_order) if display_order else 0
                )
                messages.success(request, "Đã thêm video.")
        elif action == 'edit':
            video_id = request.POST.get('video_id')
            video = YoutubeVideo.objects.filter(id=video_id).first()
            if video:
                video.title = request.POST.get('title')
                video.youtube_url = request.POST.get('youtube_url')
                video.display_order = int(request.POST.get('display_order', 0))
                video.is_active = request.POST.get('is_active') == 'on'
                video.save()
                messages.success(request, "Đã cập nhật video.")
        return redirect('client:admin_youtube_list')
    
    return render(request, 'admin_custom/youtube_management.html', {'videos': videos})

@role_required(['super_admin', 'regional_manager', 'store_admin'])
def admin_youtube_delete(request, pk):
    from apps.core.models import YoutubeVideo
    video = get_object_or_404(YoutubeVideo, pk=pk)
    if request.method == 'POST':
        video.delete()
        messages.success(request, "Đã xóa video.")
    return redirect('client:admin_youtube_list')


from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db.models.signals import pre_save
from django.db import transaction

# ==========================================
# 1. QUẢN LÝ SẢN PHẨM & DANH MỤC
# - Category: Danh mục sản phẩm (iPhone, Samsung...)
# - Product: Thông tin sản phẩm + giá + flash sale discount
# - ProductImage: Album ảnh phụ (1-N)
# - ProductVariation: Biến thể máy (màu, dung lượng, giá cộng thêm)
# ==========================================

class Category(models.Model):
    """
    Bảng Danh mục: Phân loại sản phẩm (VD: iPhone, Samsung, Xiaomi...)
    """
    name = models.CharField(max_length=100, verbose_name="Tên danh mục")
    slug = models.SlugField(unique=True, verbose_name="Đường dẫn thân thiện (URL)")

    def __str__(self):
        return self.name

class Product(models.Model):
    """
    Bảng Sản phẩm: Lưu trữ thông tin chi tiết của từng chiếc điện thoại
    """
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products', verbose_name="Danh mục")
    name = models.CharField(max_length=200, verbose_name="Tên điện thoại")
    price = models.DecimalField(max_digits=12, decimal_places=0, verbose_name="Giá bán")
    description = models.TextField(verbose_name="Mô tả tóm tắt (Thông số kỹ thuật)")
    content = models.TextField(null=True, blank=True, verbose_name="Bài viết giới thiệu chi tiết")
    image = models.ImageField(upload_to='products/', null=True, blank=True, verbose_name="Ảnh đại diện (Bìa)")
    stock = models.IntegerField(default=0, verbose_name="Số lượng tồn kho hiện tại")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Ngày tạo")

    def __str__(self):
        return self.name
    @property
    def get_discount_amount(self):
        """
        Tính số tiền giảm giá dựa trên cột 'flash_price' của bảng FlashSale.
        Chỉ tính khi Flash Sale còn hợp lệ (còn hạn & đang active).
        """
        # Kiểm tra sản phẩm có Flash Sale không VÀ Flash Sale đó còn hợp lệ không
        if hasattr(self, 'flash_sale') and self.flash_sale.is_valid():
            # Sử dụng đúng tên cột 'flash_price'
            if self.flash_sale.flash_price:
                return self.price - self.flash_sale.flash_price
        return 0

    
class ProductImage(models.Model):
    """
    Bảng Album Ảnh bổ sung: Một sản phẩm có thể có nhiều ảnh phụ (Quan hệ 1-N)
    """
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images', verbose_name="Sản phẩm")
    image = models.ImageField(upload_to='products/gallery/', verbose_name="Hình ảnh")

    def __str__(self):
        return f"Ảnh phụ của {self.product.name}"

class ProductVariation(models.Model):
    """Bảng Lựa chọn biến thể máy (Ví dụ: Màu sắc, Bộ nhớ)"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variations', verbose_name="Sản phẩm")
    color = models.CharField(max_length=50, null=True, blank=True, verbose_name="Màu sắc")
    storage = models.CharField(max_length=50, null=True, blank=True, verbose_name="Dung lượng bộ nhớ")
    additional_price = models.DecimalField(max_digits=12, decimal_places=0, default=0, verbose_name="Giá cộng thêm")
    
    class Meta:
        verbose_name = "Biến thể sản phẩm"
        verbose_name_plural = "Các biến thể sản phẩm"
        
    def __str__(self):
        color_str = self.color if self.color else ""
        storage_str = self.storage if self.storage else ""
        opts = f"{color_str} {storage_str}".strip()
        if opts:
            return f"{self.product.name} ({opts})"
        return self.product.name


# ==========================================
# 2. QUẢN LÝ BẢN ĐỒ (GIS) & CỬA HÀNG
# - Region: Khu vực địa lý
# - Store: Cửa hàng/kho (tọa độ GPS, giờ mở cửa, is_warehouse)
# ==========================================

class Region(models.Model):
    """
    Bảng Khu vực: Phân chia địa lý (VD: Miền Bắc, Miền Nam, Vùng 1...)
    """
    name = models.CharField(max_length=100, unique=True, verbose_name="Tên khu vực")
    description = models.TextField(null=True, blank=True, verbose_name="Mô tả")
    
    class Meta:
        verbose_name = "Khu vực"
        verbose_name_plural = "Các khu vực"
        
    def __str__(self):
        return self.name

class Store(models.Model):
    """
    Bảng Cửa Hàng: Lưu thông tin và tọa độ để hiển thị lên bản đồ (Store Locator)
    """
    name = models.CharField(max_length=100, verbose_name="Tên cửa hàng")
    address = models.CharField(max_length=255, verbose_name="Địa chỉ chi tiết")
    phone = models.CharField(max_length=20, null=True, blank=True, verbose_name="Hotline")
    description = models.TextField(null=True, blank=True, verbose_name="Mô tả cửa hàng")
    image = models.ImageField(upload_to='stores/', null=True, blank=True, verbose_name="Hình ảnh cửa hàng")
    
    # Tọa độ GPS phục vụ thuật toán tìm đường và tính khoảng cách
    latitude = models.FloatField(verbose_name="Vĩ độ (Latitude)")
    longitude = models.FloatField(verbose_name="Kinh độ (Longitude)")
    
    # Giờ hoạt động
    opening_time = models.TimeField(default="08:00:00", verbose_name="Giờ mở cửa")
    closing_time = models.TimeField(default="21:00:00", verbose_name="Giờ đóng cửa")

    region = models.ForeignKey(Region, on_delete=models.SET_NULL, null=True, blank=True, related_name='stores', verbose_name="Thuộc khu vực")
    is_warehouse = models.BooleanField(default=False, verbose_name="Là Kho hàng khu vực (Không bán lẻ)")

    def __str__(self):
        return self.name


# ==========================================
# 3. QUẢN LÝ GIAO DỊCH ĐƠN HÀNG (E-COMMERCE)
# - Order: Đơn hàng (trạng thái, thanh toán, cửa hàng xuất kho)
# - Signal update_profile_on_order_complete: Cộng điểm/chi tiêu khi hoàn thành, hoàn kho khi giao thất bại/hủy
# - OrderItem: Chi tiết đơn hàng (SP, biến thể, giá lúc mua, SL)
# - ReturnRequest: Yêu cầu trả hàng (lý do, ảnh, số tiền hoàn)
# - ReturnItem: Chi tiết từng SP trả
# - Signal handle_return_request_completion: Nhập kho lỗi + thu hồi điểm khi hoàn tất trả hàng
# ==========================================

class Order(models.Model):
    """
    Bảng Đơn Hàng: Lưu thông tin tổng quan khi khách hàng Checkout
    """
    STATUS_CHOICES = (
        ('pending', 'Chờ xử lý'),
        ('processing', 'Đang đóng gói'),
        ('shipped', 'Đang giao hàng'),
        ('completed', 'Hoàn thành'),
        ('cancelled', 'Đã hủy'),
        ('returned', 'Đã trả hàng'),
        ('delivery_failed', 'Giao hàng thất bại'),
    )

    PAYMENT_METHOD_CHOICES = (
        ('cod', 'Thanh toán tiền mặt khi nhận hàng (COD)'),
        ('bank_transfer', 'Chuyển khoản ngân hàng'),
    )

    PAYMENT_STATUS_CHOICES = (
        ('unpaid', 'Chưa thanh toán'),
        ('paid', 'Đã thanh toán'),
        ('refunded', 'Đã hoàn tiền'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders', null=True, blank=True, verbose_name="Khách hàng")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="Trạng thái đơn")

    # Thông tin giao hàng
    full_name = models.CharField(max_length=100, verbose_name="Họ và tên người nhận")
    address = models.CharField(max_length=255, verbose_name="Địa chỉ giao hàng")
    phone = models.CharField(max_length=20, verbose_name="Số điện thoại")
    total_price = models.DecimalField(max_digits=12, decimal_places=0, verbose_name="Tổng tiền hóa đơn")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Ngày đặt hàng")
    coupon = models.ForeignKey('Coupon', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Mã giảm giá đã dùng")
    discount_amount = models.DecimalField(max_digits=10, decimal_places=0, default=0, verbose_name="Số tiền được giảm")
    shipping_fee = models.DecimalField(max_digits=10, decimal_places=0, default=0, verbose_name="Phí giao hàng")
    fulfillment_store = models.ForeignKey(Store, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Cửa hàng xuất kho")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="Trạng thái đơn")
    is_stock_deducted = models.BooleanField(default=False, verbose_name="Đã trừ kho")

    # Payment system
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='cod', verbose_name="Phương thức thanh toán")
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='unpaid', verbose_name="Trạng thái thanh toán")
    payment_receipt = models.ImageField(upload_to='payment_receipts/', null=True, blank=True, verbose_name="Ảnh biên lai (nếu check bank)")

    def __str__(self):
        return f"Đơn hàng #{self.id} - {self.full_name}"
@receiver(pre_save, sender=Order)
def update_profile_on_order_complete(sender, instance, **kwargs):
        if instance.id: # Chỉ xét các đơn hàng đã tồn tại (đang được cập nhật)
            old_order = Order.objects.get(id=instance.id)
            
            # Kiểm tra xem đơn hàng có vừa chuyển từ trạng thái khác sang 'completed' không
            if old_order.status != 'completed' and instance.status == 'completed':
                if instance.user and hasattr(instance.user, 'profile'):
                    profile = instance.user.profile
                    # Cộng tiền
                    profile.total_spent += instance.total_price
                    # Tính điểm (100k = 1 điểm)
                    profile.points += int(instance.total_price / 100000)
                    profile.save()
            
            # Kiểm tra chuyển trạng thái sang delivery_failed
            if old_order.status != 'delivery_failed' and instance.status == 'delivery_failed':
                # Nếu đã trừ kho, thì cộng lại trả kho gốc
                if instance.is_stock_deducted and instance.fulfillment_store:
                    for item in instance.items.all():
                        stock_record = StoreStock.objects.filter(
                            store=instance.fulfillment_store, 
                            product=item.product,
                            variation=item.variation
                        ).first()
                        if stock_record:
                            stock_record.quantity += item.quantity
                            stock_record.save()
                            # Ghi log hoàn kho
                            StockTransaction.objects.create(
                                product=item.product, variation=item.variation,
                                quantity=item.quantity, transaction_type='restock',
                                store_destination=instance.fulfillment_store,
                                note=f"Hoàn kho đơn hàng giao thất bại #{instance.id}"
                            )
                    # Cập nhật không trừ kho nữa để tránh logic lặp (dùng update để không trigger signal)
                    Order.objects.filter(id=instance.id).update(is_stock_deducted=False)
                    instance.is_stock_deducted = False

            # Kiểm tra chuyển trạng thái sang cancelled
            if old_order.status != 'cancelled' and instance.status == 'cancelled':
                # Giải phóng hàng tạm giữ nếu chưa trừ kho thực tế
                if not instance.is_stock_deducted and instance.fulfillment_store:
                    for item in instance.items.all():
                        stock_record = StoreStock.objects.filter(
                            store=instance.fulfillment_store, 
                            product=item.product, variation=item.variation
                        ).first()
                        if stock_record:
                            stock_record.reserved_quantity -= item.quantity
                            if stock_record.reserved_quantity < 0:
                                stock_record.reserved_quantity = 0
                            stock_record.save()

class OrderItem(models.Model):
    """
    Bảng Chi tiết Đơn hàng: Ghi lại từng món hàng nằm trong một Đơn hàng cụ thể
    """
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items', verbose_name="Thuộc đơn hàng")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="Sản phẩm")
    variation = models.ForeignKey('ProductVariation', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Phân loại đã đặt")
    color_chosen = models.CharField(max_length=50, null=True, blank=True, verbose_name="Màu đã chọn")
    storage_chosen = models.CharField(max_length=50, null=True, blank=True, verbose_name="Dung lượng đã chọn")
    price = models.DecimalField(max_digits=12, decimal_places=0, verbose_name="Giá lúc mua")
    quantity = models.IntegerField(default=1, verbose_name="Số lượng")

    def get_total_item_price(self):
        return self.price * self.quantity

    def __str__(self):
        return f"{self.product.name} (SL: {self.quantity})"

class ReturnRequest(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Chờ duyệt'),
        ('approved', 'Đã duyệt - Chờ nhận hàng'),
        ('completed', 'Đã hoàn tiền & Nhập kho lỗi'),
        ('rejected', 'Từ chối'),
    )
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='returns', verbose_name="Đơn hàng")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='returns', verbose_name="Khách hàng")
    reason = models.TextField(verbose_name="Lý do trả hàng")
    proof_image = models.ImageField(upload_to='returns/', null=True, blank=True, verbose_name="Ảnh bằng chứng")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="Trạng thái")
    refund_amount = models.DecimalField(max_digits=12, decimal_places=0, verbose_name="Số tiền sẽ hoàn")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Ngày gửi yêu cầu")

    def __str__(self):
        return f"Yêu cầu trả hàng #{self.id} - Đơn {self.order.id}"

class ReturnItem(models.Model):
    return_request = models.ForeignKey(ReturnRequest, on_delete=models.CASCADE, related_name='items')
    order_item = models.ForeignKey(OrderItem, on_delete=models.CASCADE)
    quantity = models.IntegerField(verbose_name="Số lượng trả")
    
    def __str__(self):
        return f"Trả {self.quantity} x {self.order_item.product.name}"

@receiver(pre_save, sender=ReturnRequest)
def handle_return_request_completion(sender, instance, **kwargs):
    if instance.id:
        old_return = ReturnRequest.objects.get(id=instance.id)
        if old_return.status != 'completed' and instance.status == 'completed':
            order = instance.order
            store = order.fulfillment_store
            if store:
                for r_item in instance.items.all():
                    # Thêm vào kho hàng lỗi/cũ
                    defective_stock, created = DefectiveProductStock.objects.get_or_create(
                        store=store, 
                        product=r_item.order_item.product,
                        variation=r_item.order_item.variation,
                        defaults={'quantity': 0}
                    )
                    defective_stock.quantity += r_item.quantity
                    defective_stock.save()
                    
                    # Ghi nhận biến động kho
                    StockTransaction.objects.create(
                        product=r_item.order_item.product,
                        variation=r_item.order_item.variation,
                        quantity=r_item.quantity,
                        transaction_type='in',
                        price=0,
                        store_destination=store,
                        note=f"Nhập hàng lỗi/trả từ Yêu cầu trả hàng #{instance.id}"
                    )
                    
            # Thu hồi điểm và tổng chi tiêu
            if instance.user and hasattr(instance.user, 'profile'):
                profile = instance.user.profile
                # Giảm chi tiêu
                profile.total_spent -= instance.refund_amount
                if profile.total_spent < 0:
                    profile.total_spent = 0
                
                # Giảm điểm
                points_to_deduct = int(instance.refund_amount / 100000)
                profile.points -= points_to_deduct
                if profile.points < 0:
                    profile.points = 0
                
                profile.save()
            
            # Cập nhật trạng thái đơn hàng thành returned
            order.status = 'returned'
            order.save()


# ==========================================
# 4. QUẢN LÝ KHO HÀNG (INVENTORY/STOCK)
# - StockTransaction: Nhật ký kho (nhập/xuất/điều chuyển/cân bằng/hoàn kho)
# - StockTransfer: Phiếu điều chuyển kho giữa chi nhánh
# - StockTransferItem: Chi tiết SP trong phiếu điều chuyển
# - Stocktaking: Phiếu kiểm kê kho
# - StocktakingItem: Chi tiết kiểm kê (hệ thống vs thực tế)
# - UserProfile: Hồ sơ người dùng (RBAC, hạng thành viên, điểm)
# - Signal create_user_profile / save_user_profile: Tự động tạo profile
# - StoreStock: Tồn kho chi nhánh (quantity, reserved, available)
# - DefectiveProductStock: Tồn kho hàng lỗi/cũ
# - FlashSale: Khuyến mãi chớp nhoáng (giá flash, thời gian)
# - Coupon: Mã giảm giá (%, VNĐ, hạn, giới hạn lượt)
# - ShippingAddress: Sổ địa chỉ nhận hàng khách hàng
# - Signal auto_create_store_stock: Tự động tạo StoreStock tại Kho Tổng
# - Signal sync_master_stock_to_product: Đồng bộ tổng tồn kho → Product.stock
# - Signal deduct_stock_on_complete: Trừ kho khi đơn hoàn thành
# - Signal sync_transfer_to_store_stock: Cộng/trừ kho khi nhập/xuất
# ==========================================

class StockTransaction(models.Model):
    """
    Bảng Nhật Ký Kho: Ghi lại mọi biến động tăng/giảm số lượng của sản phẩm để chống thất thoát
    """
    TRANSACTION_TYPES = (
        ('in', 'Nhập kho (Nhập mới)'),
        ('out', 'Xuất kho (Điều chuyển)'),
        ('sale', 'Xuất bán hàng (Đơn hàng)'),
        ('return', 'Nhập trả hàng lỗi'),
        ('restock', 'Hoàn kho (Giao thất bại)'),
        ('transfer_out', 'Xuất điều chuyển đi'),
        ('transfer_in', 'Nhận điều chuyển đến'),
        ('inventory_loss', 'Xuất cân bằng kho (Hao hụt)'),
        ('inventory_gain', 'Nhập cân bằng kho (Dư thừa)'),
    )

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='stock_history', verbose_name="Sản phẩm giao dịch")
    variation = models.ForeignKey('ProductVariation', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Biến thể giao dịch")
    quantity = models.IntegerField(verbose_name="Số lượng thay đổi")
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES, verbose_name="Loại giao dịch")
    price = models.DecimalField(max_digits=12, decimal_places=0, default=0, verbose_name="Giá nhập đơn vị (Nếu là Nhập kho)")
    
    # Chỉ áp dụng nếu xuất kho đi cửa hàng khác
    store_destination = models.ForeignKey(Store, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Cửa hàng nhận (Nếu là Xuất kho)")
    
    note = models.TextField(blank=True, null=True, verbose_name="Ghi chú/Lý do")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="Nhân viên thực hiện")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Thời gian thực hiện")

    class Meta:
        verbose_name = "Giao dịch kho"
        verbose_name_plural = "Lịch sử giao dịch kho"
        ordering = ['-created_at'] # Sắp xếp giảm dần (Mới nhất lên đầu)

    def __str__(self):
        return f"#{self.id} | {self.get_transaction_type_display()} - {self.product.name} (SL: {self.quantity})"

    def get_total_value(self):
        """Hàm tính tổng giá trị của một lần nhập kho"""
        return self.quantity * self.price

class StockTransfer(models.Model):
    """
    Bảng Phiếu Điều Chuyển Kho: Luân chuyển hàng hóa giữa các chi nhánh
    """
    STATUS_CHOICES = (
        ('pending', 'Chờ duyệt xuất'),
        ('shipping', 'Đang vận chuyển'),
        ('completed', 'Đã nhận hàng'),
        ('cancelled', 'Đã hủy'),
    )
    
    code = models.CharField(max_length=20, unique=True, verbose_name="Mã phiếu")
    from_store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='transfers_out', verbose_name="Từ kho")
    to_store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='transfers_in', verbose_name="Đến kho")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="Trạng thái")
    note = models.TextField(blank=True, null=True, verbose_name="Ghi chú")
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='transfers_created', verbose_name="Người tạo")
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='transfers_approved', verbose_name="Người duyệt xuất")
    received_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='transfers_received', verbose_name="Người nhận hàng")
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Ngày tạo")
    shipped_at = models.DateTimeField(null=True, blank=True, verbose_name="Ngày xuất kho")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="Ngày nhận hàng")

    class Meta:
        verbose_name = "Phiếu điều chuyển kho"
        verbose_name_plural = "Các phiếu điều chuyển kho"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.code} ({self.from_store.name} -> {self.to_store.name})"

class StockTransferItem(models.Model):
    transfer = models.ForeignKey(StockTransfer, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="Sản phẩm")
    variation = models.ForeignKey('ProductVariation', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Biến thể")
    quantity = models.IntegerField(verbose_name="Số lượng điều chuyển")
    
    def __str__(self):
        return f"{self.quantity} x {self.product.name} - {self.transfer.code}"

class Stocktaking(models.Model):
    """
    Bảng Phiếu Kiểm Kê Kho: Chốt số lượng đếm tay thực tế so với phần mềm
    """
    STATUS_CHOICES = (
        ('draft', 'Bản nháp / Đang đếm'),
        ('approved', 'Đã duyệt / Đã cân bằng'),
        ('cancelled', 'Đã hủy'),
    )
    
    code = models.CharField(max_length=20, unique=True, verbose_name="Mã phiếu kiểm kê")
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='stocktakings', verbose_name="Cửa hàng")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', verbose_name="Trạng thái")
    note = models.TextField(blank=True, null=True, verbose_name="Ghi chú")
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_stocktakings', verbose_name="Người tạo")
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_stocktakings', verbose_name="Người duyệt")
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Ngày tạo")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Cập nhật lần cuối")

    class Meta:
        verbose_name = "Phiếu kiểm kê"
        verbose_name_plural = "Các phiếu kiểm kê"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.code} - {self.store.name}"

class StocktakingItem(models.Model):
    stocktaking = models.ForeignKey(Stocktaking, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="Sản phẩm")
    variation = models.ForeignKey('ProductVariation', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Biến thể")
    
    system_quantity = models.IntegerField(verbose_name="Tồn kho phần mềm")
    actual_quantity = models.IntegerField(verbose_name="Tồn kho thực tế (đếm tay)")
    discrepancy = models.IntegerField(verbose_name="Chênh lệch", default=0) # actual - system
    
    def save(self, *args, **kwargs):
        self.discrepancy = self.actual_quantity - self.system_quantity
        super().save(*args, **kwargs)
        
    def __str__(self):
        return f"{self.product.name} (Hệ thống: {self.system_quantity}, Thực tế: {self.actual_quantity})"
    
class UserProfile(models.Model):
    ROLE_CHOICES = (
        ('super_admin', 'Admin Toàn Quốc'),
        ('regional_manager', 'Quản lý Vùng'),
        ('store_admin', 'Quản lý Cửa hàng'),
        ('warehouse_keeper', 'Thủ kho'),
        ('sales_staff', 'Nhân viên bán hàng'),
        ('customer', 'Khách hàng'),
    )

    # 1. THÔNG TIN CƠ BẢN
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True, verbose_name="Ảnh đại diện")
    phone = models.CharField(max_length=15, blank=True, verbose_name="Số điện thoại")
    address = models.TextField(blank=True, verbose_name="Địa chỉ")

    # 2. PHÂN QUYỀN HỆ THỐNG
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='customer', verbose_name="Vai trò")
    region = models.ForeignKey('Region', on_delete=models.SET_NULL, null=True, blank=True,
                               related_name='managers', verbose_name="Quản lý khu vực (Dành cho Quản lý vùng)")
    store = models.ForeignKey('Store', on_delete=models.SET_NULL, null=True, blank=True, 
                                 related_name='employees', verbose_name="Trực thuộc cửa hàng/kho")

    # 3. HỆ THỐNG THÀNH VIÊN (STYLE HOÀNG HÀ)
    total_spent = models.DecimalField(max_digits=12, decimal_places=0, default=0, verbose_name="Tổng chi tiêu")
    points = models.IntegerField(default=0, verbose_name="Điểm tích lũy")
    
    @property
    def rank(self):
        """Tự động tính hạng thành viên dựa trên tổng chi tiêu"""
        if self.total_spent >= 50000000:
            return "GOLD"
        elif self.total_spent >= 10000000:
            return "SILVER"
        elif self.total_spent > 0:
            return "MEMBER"
        return "NEW"

    @property
    def next_rank_threshold(self):
        """Tính số tiền cần thêm để lên hạng tiếp theo"""
        if self.rank == "NEW" or self.rank == "MEMBER":
            return 10000000 - self.total_spent
        elif self.rank == "SILVER":
            return 50000000 - self.total_spent
        return 0

    def __str__(self):
        return f"{self.user.username} - {self.get_role_display()}"

    class Meta:
        verbose_name = "Hồ sơ người dùng"
        verbose_name_plural = "Hồ sơ người dùng"

# --- SIGNAL: Tự động tạo UserProfile khi User được tạo ---
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()

class StoreStock(models.Model):
    """
    Bảng Tồn Kho Chi Nhánh: Quản lý số lượng cụ thể của từng sản phẩm tại từng cửa hàng
    """
    store = models.ForeignKey('Store', on_delete=models.CASCADE, related_name='inventory', verbose_name="Cửa hàng")
    product = models.ForeignKey('Product', on_delete=models.CASCADE, related_name='store_stocks', verbose_name="Sản phẩm")
    variation = models.ForeignKey('ProductVariation', on_delete=models.CASCADE, null=True, blank=True, verbose_name="Biến thể")
    quantity = models.IntegerField(default=0, verbose_name="Tồn kho thực tế (Physical)")
    reserved_quantity = models.IntegerField(default=0, verbose_name="Hàng tạm giữ (Reserved)")

    @property
    def available_quantity(self):
        """Số lượng khả dụng để bán = Tồn kho thực tế - Hàng tạm giữ"""
        return max(0, self.quantity - self.reserved_quantity)

    class Meta:
        # Đảm bảo 1 biến thể ở 1 cửa hàng chỉ có 1 dòng ghi tồn kho
        unique_together = ('store', 'product', 'variation')
        verbose_name = "Tồn kho chi nhánh"
        verbose_name_plural = "Tồn kho các chi nhánh"

    def __str__(self):
        return f"{self.store.name} - {self.product.name}: {self.quantity}"

class DefectiveProductStock(models.Model):
    """Lưu trữ số lượng hàng bị lỗi hoặc cũ do khách hàng trả về sau khi đã nhận"""
    store = models.ForeignKey('Store', on_delete=models.CASCADE, related_name='defective_inventory', verbose_name="Cửa hàng")
    product = models.ForeignKey('Product', on_delete=models.CASCADE, related_name='defective_stocks', verbose_name="Sản phẩm")
    variation = models.ForeignKey('ProductVariation', on_delete=models.CASCADE, null=True, blank=True, verbose_name="Biến thể")
    quantity = models.IntegerField(default=0, verbose_name="Tồn kho hàng lỗi/cũ")

    class Meta:
        unique_together = ('store', 'product', 'variation')
        verbose_name = "Tồn kho hàng lỗi/cũ"
        verbose_name_plural = "Tồn kho hàng lỗi/cũ các chi nhánh"

    def __str__(self):
        return f"Hàng lỗi - {self.store.name} - {self.product.name}: {self.quantity}"

class FlashSale(models.Model):
    """
    Bảng Khuyến Mãi Chớp Nhoáng (Flash Sale): Quản lý giá giảm và thời gian đếm ngược
    """
    # Dùng OneToOneField vì mỗi thời điểm, 1 sản phẩm chỉ nên có 1 mức giá Flash Sale
    product = models.OneToOneField(
        'Product', 
        on_delete=models.CASCADE, 
        related_name='flash_sale', 
        verbose_name="Sản phẩm áp dụng"
    )
    flash_price = models.DecimalField(
        max_digits=12, 
        decimal_places=0, 
        verbose_name="Giá Flash Sale (VNĐ)"
    )
    end_time = models.DateTimeField(verbose_name="Thời gian kết thúc")
    is_active = models.BooleanField(default=True, verbose_name="Trạng thái kích hoạt")

    class Meta:
        verbose_name = "Chương trình Flash Sale"
        verbose_name_plural = "Các chương trình Flash Sale"

    def is_valid(self):
        """
        Hàm kiểm tra xem Flash Sale còn hợp lệ không.
        Điều kiện: is_active = True VÀ thời gian hiện tại vẫn chưa vượt quá end_time
        """
        return self.is_active and self.end_time > timezone.now()

    def __str__(self):
        return f"Flash Sale: {self.product.name}"
    
class Coupon(models.Model):
    """
    Bảng quản lý Mã Giảm Giá cho đơn hàng
    """
    DISCOUNT_CHOICES = (
        ('percent', 'Phần trăm (%)'),
        ('fixed', 'Tiền mặt (VNĐ)'),
    )
    
    code = models.CharField(max_length=50, unique=True, verbose_name="Mã giảm giá")
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_CHOICES, default='fixed', verbose_name="Loại giảm giá")
    discount_value = models.DecimalField(max_digits=10, decimal_places=0, verbose_name="Giá trị giảm")
    min_purchase = models.DecimalField(max_digits=12, decimal_places=0, default=0, verbose_name="Đơn hàng tối thiểu")
    
    valid_from = models.DateTimeField(verbose_name="Ngày bắt đầu")
    valid_to = models.DateTimeField(verbose_name="Ngày kết thúc")
    
    usage_limit = models.IntegerField(default=100, verbose_name="Giới hạn số lượt dùng")
    used_count = models.IntegerField(default=0, verbose_name="Số lượt đã dùng")
    active = models.BooleanField(default=True, verbose_name="Trạng thái")
    

    class Meta:
        verbose_name = "Mã giảm giá"
        verbose_name_plural = "Các mã giảm giá"

    def __str__(self):
        return self.code

    def is_valid(self):
        """Kiểm tra mã còn hạn, còn lượt và đang kích hoạt hay không"""
        now = timezone.now()
        return self.active and (self.valid_from <= now <= self.valid_to) and (self.used_count < self.usage_limit)
    

class ShippingAddress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='shipping_addresses', verbose_name="Người dùng")
    receiver_name = models.CharField(max_length=100, verbose_name="Tên người nhận")
    phone_number = models.CharField(max_length=15, verbose_name="Số điện thoại")
    # Lưu gộp tỉnh/huyện/xã (Ví dụ: "Phường Tân Chánh Hiệp, Quận 12, TP. Hồ Chí Minh")
    area_info = models.CharField(max_length=255, blank=True, null=True, verbose_name="Khu vực (Tỉnh/Huyện/Xã)") 
    address_detail = models.TextField(verbose_name="Địa chỉ chi tiết")
    is_default = models.BooleanField(default=False, verbose_name="Địa chỉ mặc định")

    class Meta:
        verbose_name = "Địa chỉ nhận hàng"
        verbose_name_plural = "Sổ địa chỉ khách hàng"
        ordering = ['-is_default', '-id'] # Ưu tiên hiện mặc định lên trước

    def save(self, *args, **kwargs):
        if self.is_default:
            ShippingAddress.objects.filter(user=self.user).update(is_default=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.receiver_name} - {self.address_detail}"
    

# (Thuộc section 4 - SIGNAL: Tự động tạo StoreStock tại Kho Tổng)
@receiver(post_save, sender=Product)
def auto_create_store_stock_for_product(sender, instance, created, **kwargs):
    """
    Khi tạo hoặc cập nhật Product, tự động tạo bản ghi StoreStock tại Kho Tổng
    (với quantity=0) nếu chưa tồn tại. Đảm bảo sản phẩm luôn hiển thị trong
    trang Quản lý Kho Hàng.
    """
    main_warehouse = Store.objects.filter(is_warehouse=True).first()
    if main_warehouse:
        variations = list(instance.variations.all())
        if variations:
            # Sản phẩm CÓ biến thể → tạo bản ghi cho từng variation
            for variation in variations:
                StoreStock.objects.get_or_create(
                    store=main_warehouse,
                    product=instance,
                    variation=variation,
                    defaults={'quantity': 0}
                )
        else:
            # Sản phẩm KHÔNG có biến thể → tạo bản ghi chung (variation=None)
            StoreStock.objects.get_or_create(
                store=main_warehouse,
                product=instance,
                variation=None,
                defaults={'quantity': 0}
            )

@receiver(post_save, sender=ProductVariation)
def auto_create_store_stock_for_variation(sender, instance, created, **kwargs):
    """
    Khi tạo hoặc cập nhật ProductVariation, tự động tạo bản ghi StoreStock
    tại Kho Tổng cho biến thể đó nếu chưa tồn tại.
    """
    main_warehouse = Store.objects.filter(is_warehouse=True).first()
    if main_warehouse:
        StoreStock.objects.get_or_create(
            store=main_warehouse,
            product=instance.product,
            variation=instance,
            defaults={'quantity': 0}
        )


# Lưu ý: Thay chữ 'quantity' bằng tên cột lưu số lượng trong StoreStock của bạn (có thể là 'stock')
from .models import Order, StoreStock, Product
@receiver(post_save, sender=StoreStock)
@receiver(post_delete, sender=StoreStock)
def sync_master_stock_to_product(sender, instance, **kwargs):
    """
    Tự động đồng bộ TỔNG Tồn kho của tất cả chi nhánh ra ngoài Trang chủ (Product.stock)
    Dùng .update() thay vì .save() để KHÔNG kích hoạt lại post_save trên Product (tránh vòng lặp)
    """
    from django.db.models import Sum
    product = instance.product
    
    # Tính tổng tồn kho của sản phẩm này trên toàn hệ thống
    total_stock = StoreStock.objects.filter(product=product).aggregate(total=Sum('quantity'))['total'] or 0
    
    # Cập nhật số lượng bằng .update() để tránh trigger post_save lại
    Product.objects.filter(id=product.id).update(stock=total_stock)
#
@receiver(post_save, sender=Order)
def deduct_stock_on_complete(sender, instance, created, **kwargs):
    # CHỈ CHẠY KHI: Trạng thái là completed VÀ chưa từng trừ kho trước đây
    if instance.status == 'completed' and not instance.is_stock_deducted:
        with transaction.atomic(): 
            items = instance.items.all() 
            store = instance.fulfillment_store
            
            if not store:
                return 

            for item in items:
                stock_record = StoreStock.objects.filter(
                    store=store, 
                    product=item.product,
                    variation=item.variation
                ).first()
                
                if stock_record:
                    # Trừ kho thực tế
                    stock_record.quantity -= item.quantity
                    # Giải phóng hàng tạm giữ
                    stock_record.reserved_quantity -= item.quantity
                    if stock_record.reserved_quantity < 0:
                        stock_record.reserved_quantity = 0
                    stock_record.save()
                    
                    # Ghi log xuất bán
                    StockTransaction.objects.create(
                        product=item.product,
                        variation=item.variation,
                        quantity=item.quantity,
                        transaction_type='sale',
                        store_destination=store,
                        note=f"Xuất bán đơn hàng #{instance.id}"
                    )
                    
            # ĐÁNH DẤU LÀ ĐÃ TRỪ KHO
            Order.objects.filter(id=instance.id).update(is_stock_deducted=True)

@receiver(post_save, sender=StockTransaction)
def sync_transfer_to_store_stock(sender, instance, created, **kwargs):
    """
    1. Tự động thêm hàng vào KHO TỔNG khi Admin làm lệnh Nhập kho ('in').
    2. Tự động cộng số lượng vào bảng StoreStock của chi nhánh 
    mỗi khi Admin làm lệnh điều chuyển (Xuất kho 'out') đến chi nhánh đó.
    LƯU Ý: Nếu là xuất kho cho chi nhánh, hệ thống sẽ tự động TRỪ số lượng ở Kho Tổng.
    """
    if created:
        # Trường hợp 1: Hành động NHẬP KHO CHUNG
        if instance.transaction_type == 'in':
            main_warehouse = Store.objects.filter(is_warehouse=True).first()
            if main_warehouse:
                stock_record, is_new = StoreStock.objects.get_or_create(
                    store=main_warehouse,
                    product=instance.product,
                    variation=instance.variation,
                    defaults={'quantity': 0}
                )
                stock_record.quantity += instance.quantity
                stock_record.save()
                
        # Trường hợp 2: Lệnh XUẤT KHO (ĐIỀU CHUYỂN) ĐẾN CHI NHÁNH
        elif instance.transaction_type == 'out' and instance.store_destination:
            # 2.1 TRỪ HÀNG TẠI KHO TỔNG
            main_warehouse = Store.objects.filter(is_warehouse=True).first()
            if main_warehouse:
                main_stock = StoreStock.objects.filter(
                    store=main_warehouse, 
                    product=instance.product,
                    variation=instance.variation
                ).first()
                if main_stock:
                    main_stock.quantity -= instance.quantity
                    if main_stock.quantity < 0:
                        main_stock.quantity = 0
                    main_stock.save()

            # 2.2 CỘNG HÀNG TẠI CHI NHÁNH NHẬN
            stock_record, is_new = StoreStock.objects.get_or_create(
                store=instance.store_destination,
                product=instance.product,
                variation=instance.variation,
                defaults={'quantity': 0}
            )
            stock_record.quantity += instance.quantity 
            stock_record.save()

# ==========================================
# 5. ĐÁNH GIÁ SẢN PHẨM (REVIEWS)
# - Review: Đánh giá SP (rating 1-5, comment, admin_reply)
# ==========================================
class Review(models.Model):
    """
    Bảng Đánh giá Sản phẩm: Lưu trữ phản hồi và xếp hạng từ khách hàng
    """
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews', verbose_name="Sản phẩm")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="Người dùng bình luận")
    rating = models.IntegerField(default=5, verbose_name="Số sao (1-5)")
    comment = models.TextField(verbose_name="Nội dung đánh giá")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Ngày đánh giá")
    
    # Phần dành cho phản hồi từ Admin/Staff
    admin_reply = models.TextField(verbose_name="Phúc đáp từ cửa hàng", blank=True, null=True)
    reply_created_at = models.DateTimeField(verbose_name="Thời gian phúc đáp", blank=True, null=True)

    class Meta:
        verbose_name = "Đánh giá sản phẩm"
        verbose_name_plural = "Đánh giá sản phẩm"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username if self.user else 'Ẩn danh'} - {self.product.name} ({self.rating} sao)"


# ==========================================
# 6. Ý KIẾN KHÁCH HÀNG (FEEDBACK/CONTACT)
# - Feedback: Góp ý/thắc mắc từ trang liên hệ (chủ đề, trạng thái)
# ==========================================
class Feedback(models.Model):
    """
    Bảng Ý Kiến Khách Hàng: Lưu trữ các góp ý, thắc mắc gửi từ trang Contact
    """
    TOPIC_CHOICES = (
        ('product',  'Hỏi về sản phẩm'),
        ('order',    'Hỏi về đơn hàng'),
        ('warranty', 'Bảo hành / Sửa chữa'),
        ('shipping', 'Vận chuyển / Giao hàng'),
        ('other',    'Khác'),
    )
    STATUS_CHOICES = (
        ('new',     'Mới'),
        ('read',    'Đã đọc'),
        ('replied', 'Đã phản hồi'),
    )

    user        = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='feedbacks', verbose_name="Tài khoản (nếu có)")
    name        = models.CharField(max_length=100, verbose_name="Họ và tên")
    email       = models.EmailField(verbose_name="Email liên hệ")
    phone       = models.CharField(max_length=20, blank=True, verbose_name="Số điện thoại")
    topic       = models.CharField(max_length=20, choices=TOPIC_CHOICES, default='other', verbose_name="Chủ đề")
    message     = models.TextField(verbose_name="Nội dung")
    status      = models.CharField(max_length=10, choices=STATUS_CHOICES, default='new', verbose_name="Trạng thái")
    created_at  = models.DateTimeField(auto_now_add=True, verbose_name="Thời gian gửi")

    class Meta:
        verbose_name = "Ý kiến khách hàng"
        verbose_name_plural = "Ý kiến khách hàng"
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.get_topic_display()}] {self.name} - {self.email}"


# ==========================================
# 7. THÔNG BÁO ĐƠN HÀNG (NOTIFICATIONS)
# - Notification: Thông báo trạng thái đơn (placed/shipped/completed/cancelled)
# ==========================================
class Notification(models.Model):
    """
    Bảng Thông Báo: Lưu thông báo trạng thái đơn hàng gửi đến khách hàng
    """
    TYPE_CHOICES = (
        ('order_placed',    'Đặt hàng thành công'),
        ('order_shipped',   'Đang giao hàng'),
        ('order_completed', 'Đơn hàng hoàn thành'),
        ('order_cancelled', 'Đơn hàng đã hủy'),
    )

    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications', verbose_name="Người nhận")
    notif_type = models.CharField(max_length=30, choices=TYPE_CHOICES, verbose_name="Loại thông báo")
    order      = models.ForeignKey('Order', on_delete=models.CASCADE, null=True, blank=True,
                                   related_name='notifications', verbose_name="Đơn hàng liên quan")
    message    = models.CharField(max_length=500, verbose_name="Nội dung thông báo")
    is_read    = models.BooleanField(default=False, verbose_name="Đã đọc")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Thời gian tạo")

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Thông báo"
        verbose_name_plural = "Thông báo"

    def __str__(self):
        return f"[{self.get_notif_type_display()}] {self.user.username} – Đơn #{self.order_id}"

    def get_icon(self):
        icons = {
            'order_placed':    'fa-check-circle',
            'order_shipped':   'fa-shipping-fast',
            'order_completed': 'fa-star',
            'order_cancelled': 'fa-times-circle',
        }
        return icons.get(self.notif_type, 'fa-bell')

    def get_color(self):
        colors = {
            'order_placed':    '#009981',
            'order_shipped':   '#0d6efd',
            'order_completed': '#ffc107',
            'order_cancelled': '#dc3545',
        }
        return colors.get(self.notif_type, '#6c757d')

# ==========================================
# 8. TIN TỨC (NEWS / BLOG)
# - NewsCategory: Danh mục tin tức (auto-slug)
# - NewsArticle: Bài viết (thumbnail, views, is_published, is_pinned, auto-slug)
# - NewsComment: Bình luận bài viết
# - Event: Sự kiện sắp tới (ngày, địa điểm)
# - YoutubeVideo: Video YouTube (carousel sidebar)
# ==========================================
class NewsCategory(models.Model):
    name = models.CharField(max_length=100, verbose_name="Tên danh mục")
    slug = models.SlugField(max_length=150, unique=True, blank=True)

    class Meta:
        verbose_name = "Danh mục tin tức"
        verbose_name_plural = "Các danh mục tin tức"

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

class NewsArticle(models.Model):
    title = models.CharField(max_length=255, verbose_name="Tiêu đề")
    slug = models.SlugField(max_length=300, unique=True, blank=True)
    category = models.ForeignKey(NewsCategory, on_delete=models.SET_NULL, null=True, related_name='articles', verbose_name="Danh mục")
    thumbnail = models.ImageField(upload_to='news/%Y/%m/', null=True, blank=True, verbose_name="Ảnh đại diện (Thumbnail)")
    short_description = models.TextField(verbose_name="Mô tả ngắn")
    content = models.TextField(verbose_name="Nội dung bài viết")
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="Tác giả")
    views = models.PositiveIntegerField(default=0, verbose_name="Lượt xem")
    is_published = models.BooleanField(default=True, verbose_name="Đã xuất bản")
    is_pinned = models.BooleanField(default=False, verbose_name="Ghim bài viết")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Ngày đăng")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Cập nhật lần cuối")

    class Meta:
        ordering = ['-is_pinned', '-created_at']
        verbose_name = "Bài viết tin tức"
        verbose_name_plural = "Các bài viết tin tức"

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            base_slug = slugify(self.title)
            slug = base_slug
            counter = 1
            while NewsArticle.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

class NewsComment(models.Model):
    article = models.ForeignKey(NewsArticle, on_delete=models.CASCADE, related_name='comments', verbose_name="Bài viết")
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Người dùng")
    content = models.TextField(verbose_name="Nội dung bình luận")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Thời gian bình luận")

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Bình luận tin tức"
        verbose_name_plural = "Các bình luận tin tức"

    def __str__(self):
        return f"{self.user.username} - {self.article.title}"


class Event(models.Model):
    """Sự kiện sắp tới - hiển thị sidebar tin tức"""
    title = models.CharField(max_length=255, verbose_name="Tên sự kiện")
    event_date = models.DateField(verbose_name="Ngày diễn ra")
    location = models.CharField(max_length=255, verbose_name="Địa điểm")
    description = models.TextField(blank=True, verbose_name="Mô tả ngắn")
    article = models.ForeignKey(NewsArticle, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='events', verbose_name="Bài viết liên kết")
    is_active = models.BooleanField(default=True, verbose_name="Đang hiển thị")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['event_date']
        verbose_name = "Sự kiện"
        verbose_name_plural = "Các sự kiện"

    def __str__(self):
        return f"{self.title} - {self.event_date}"


class YoutubeVideo(models.Model):
    """Video YouTube - hiển thị carousel sidebar tin tức"""
    title = models.CharField(max_length=255, verbose_name="Tiêu đề video")
    youtube_url = models.URLField(verbose_name="Link YouTube")
    is_active = models.BooleanField(default=True, verbose_name="Đang hiển thị")
    display_order = models.IntegerField(default=0, verbose_name="Thứ tự hiển thị")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['display_order', '-created_at']
        verbose_name = "Video YouTube"
        verbose_name_plural = "Các video YouTube"

    @property
    def video_id(self):
        """Trích xuất video ID từ URL YouTube"""
        url = self.youtube_url
        if 'youtu.be/' in url:
            return url.split('youtu.be/')[-1].split('?')[0]
        elif 'watch?v=' in url:
            return url.split('watch?v=')[-1].split('&')[0]
        elif 'embed/' in url:
            return url.split('embed/')[-1].split('?')[0]
        elif 'shorts/' in url:
            return url.split('shorts/')[-1].split('?')[0]
        return url

    @property
    def embed_url(self):
        """Embed URL (nocookie)"""
        return f"https://www.youtube-nocookie.com/embed/{self.video_id}?rel=0"

    @property
    def thumbnail_url(self):
        """Lấy thumbnail từ YouTube"""
        return f"https://img.youtube.com/vi/{self.video_id}/hqdefault.jpg"

    @property
    def watch_url(self):
        """Link xem trực tiếp trên YouTube"""
        return f"https://www.youtube.com/watch?v={self.video_id}"

    def __str__(self):
        return self.title
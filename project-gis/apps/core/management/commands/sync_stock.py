from django.core.management.base import BaseCommand
from apps.core.models import Product, Store, StoreStock


class Command(BaseCommand):
    help = 'Đồng bộ tất cả sản phẩm hiện có vào bảng StoreStock tại Kho Tổng (backfill)'

    def handle(self, *args, **options):
        main_warehouse = Store.objects.filter(is_warehouse=True).first()
        if not main_warehouse:
            self.stderr.write(self.style.ERROR(
                '❌ Không tìm thấy Kho Tổng (is_warehouse=True). '
                'Hãy đánh dấu 1 cửa hàng là Kho Tổng trước.'
            ))
            return

        products = Product.objects.prefetch_related('variations').all()
        created_count = 0
        skipped_count = 0

        for product in products:
            variations = list(product.variations.all())

            if variations:
                # Sản phẩm CÓ biến thể → tạo bản ghi cho từng variation
                for variation in variations:
                    _, created = StoreStock.objects.get_or_create(
                        store=main_warehouse,
                        product=product,
                        variation=variation,
                        defaults={'quantity': 0}
                    )
                    if created:
                        created_count += 1
                    else:
                        skipped_count += 1
            else:
                # Sản phẩm KHÔNG có biến thể → tạo bản ghi chung
                _, created = StoreStock.objects.get_or_create(
                    store=main_warehouse,
                    product=product,
                    variation=None,
                    defaults={'quantity': 0}
                )
                if created:
                    created_count += 1
                else:
                    skipped_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'✅ Hoàn tất! Đã tạo {created_count} bản ghi StoreStock mới tại "{main_warehouse.name}". '
            f'Bỏ qua {skipped_count} bản ghi đã tồn tại.'
        ))

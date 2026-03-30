from django.db import models
from django.contrib.auth.models import User

# Bảng thông tin khách hàng
class Customer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    full_name = models.CharField(max_length=200, verbose_name="Họ tên")
    address = models.TextField(verbose_name="Địa chỉ")
    phone = models.CharField(max_length=15, verbose_name="Số điện thoại")

    def __str__(self):
        return self.full_name
    from django.db import models


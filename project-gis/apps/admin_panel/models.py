from django.db import models

# Bảng lưu lịch sử hoạt động quản trị
class AdminActivity(models.Model):
    activity_name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.activity_name
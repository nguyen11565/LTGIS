"""
URL configuration for webbanhang project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
# from django.contrib import admin
# from django.urls import path, include

# urlpatterns = [
#     path('admin/', admin.site.urls), # Đảm bảo dòng này TRỎ ĐÚNG vào admin.site.urls
#     path('', include('apps.client.urls')),
#     path('admin_panel/', include('apps.admin_panel.urls')), # Nếu bạn có trang admin riêng thì đổi tên prefix này
    
# ]
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    # Thêm namespace='client' vào đây để Django hiểu ngay lập tức
path('', include(('apps.client.urls', 'client'), namespace='client')),
]

# Thêm đoạn này để Django hiển thị ảnh khi đang chạy thử nghiệm (DEBUG=True)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
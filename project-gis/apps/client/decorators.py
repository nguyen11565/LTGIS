from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps

def role_required(allowed_roles=[]):
    """
    Decorator kiểm tra xem User có nằm trong danh sách role được phép không.
    VD: @role_required(['super_admin', 'store_admin'])
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            # Kiểm tra đăng nhập
            if not request.user.is_authenticated:
                return redirect('client:login')
            
            # Kiểm tra quyền
            user_role = request.user.profile.role
            if user_role in allowed_roles:
                return view_func(request, *args, **kwargs)
            else:
                messages.error(request, "Bạn không có quyền truy cập trang này!")
                # Nếu là khách thì đuổi về trang chủ, nếu là nhân viên thì đuổi về dashboard
                if user_role == 'customer':
                    return redirect('client:home')
                return redirect('client:admin_dashboard')
                
        return _wrapped_view
    return decorator
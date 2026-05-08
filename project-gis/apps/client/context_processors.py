from apps.core.models import Notification


def notifications_context(request):
    """
    Inject unread notification count và recent notifications vào mọi template.
    Chỉ hoạt động khi user đã đăng nhập.
    """
    if request.user.is_authenticated:
        unread_count = Notification.objects.filter(
            user=request.user, is_read=False
        ).count()
        recent_notifications = Notification.objects.filter(
            user=request.user
        ).select_related('order')[:6]
        return {
            'notif_unread_count': unread_count,
            'recent_notifications': recent_notifications,
        }
    return {
        'notif_unread_count': 0,
        'recent_notifications': [],
    }

from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger


def paginate_queryset(request, queryset, per_page=12):
    """
    Hàm phân trang dùng chung cho toàn project
    
    :param request: request từ view
    :param queryset: dữ liệu cần phân trang (QuerySet)
    :param per_page: số item mỗi trang (mặc định 12)
    :return: page_obj, paginator
    """
    paginator = Paginator(queryset, per_page)
    page_number = request.GET.get('page')

    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    return page_obj, paginator
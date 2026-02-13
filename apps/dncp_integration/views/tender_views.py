from django.views.decorators.http import require_http_methods

from apps.dncp_integration.views import api_views, local_views


@require_http_methods(["GET"])
def tender_list(request):
    return local_views.tender_list(request)


@require_http_methods(["GET"])
def tender_detail(request, ocid):
    return local_views.tender_detail(request, ocid)

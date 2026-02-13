from django.urls import path

from apps.dncp_integration.views import api_views

app_name = "dncp_api"

urlpatterns = [
    path("search/", api_views.dncp_list, name="dncp_list"),
    path("import/", api_views.dncp_import, name="dncp_import"),
    path("import/bulk/", api_views.dncp_import_bulk, name="dncp_import_bulk"),
    path("<str:ocid>/", api_views.dncp_detail, name="dncp_detail"),
]

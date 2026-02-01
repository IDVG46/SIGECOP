from django.urls import path
from . import views

app_name = "dncp_integration"

urlpatterns = [
    path("", views.dncp_list, name="dncp_list"),
    path("<str:ocid>/", views.dncp_detail, name="dncp_detail"),
]
from django.urls import path
from . import views

app_name = "dncp_integration"

urlpatterns = [
    path("list/", views.procesos_licitacion, name="dncp_list"),
    path("detail/<str:ocid>/", views.dncp_detail, name="dncp_detail"),
]
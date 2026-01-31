from django.urls import path
from . import views

app_name = "dncp_integration"

urlpatterns = [
    path("list/", views.procesos_licitacion, name="dncp_list"),
]
from django.urls import path

from . import api

app_name = "products"

urlpatterns = [
    path("", api.product_list, name="list"),
    path("<slug:slug>/", api.product_detail, name="detail"),
]

from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("products/", views.shop, name="shop"),
    path("cart/", views.cart, name="cart"),
    path("checkout/", views.checkout, name="checkout"),
    path("orders/track/", views.order_tracking, name="tracking"),
    path("account/", views.account, name="account"),
    path("demo-admin/", views.demo_admin, name="demo_admin"),
    path("healthz/", views.healthz, name="healthz"),
<<<<<<< HEAD
    path('employees/', views.employee_list, name='employee_list'),
=======
>>>>>>> 7cb3a3d624346f16c1173c5d42a2a40b1258bf50
]

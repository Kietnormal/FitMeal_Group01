from decimal import Decimal

from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase
from django.urls import reverse

from .admin import ProductAdmin
from .forms import ProductCreateForm
from .models import Product, ProductActivity


class ProductModelTests(TestCase):
    def test_product_saves_catalog_and_nutrition_fields(self):
        product = Product.objects.create(
            sku="FM-001",
            slug="uc-gao-lut",
            name="Ức gà gạo lứt",
            category=Product.Category.MEAL,
            description="Bữa ăn giàu protein",
            price=Decimal("89000.00"),
            calories=420,
            protein=Decimal("35.50"),
            carbs=Decimal("42.00"),
            fat=Decimal("9.25"),
        )

        self.assertEqual(Product.objects.get(pk=product.pk).price, Decimal("89000.00"))
        self.assertEqual(str(product), "Ức gà gạo lứt (FM-001)")

    def test_price_must_be_greater_than_zero(self):
        product = Product(
            sku="FM-002",
            slug="mon-mien-phi",
            name="Món miễn phí",
            category=Product.Category.MEAL,
            description="Sản phẩm kiểm tra giá",
            price=Decimal("0"),
        )

        with self.assertRaises(ValidationError):
            product.full_clean()

    def test_dry_goods_requires_shipping_weight(self):
        product = Product(
            sku="FM-DRY-TEST",
            slug="dry-goods-test",
            name="Đồ khô kiểm tra",
            category=Product.Category.DRY_GOODS,
            description="Sản phẩm kiểm tra",
            price=Decimal("50000"),
        )

        with self.assertRaises(ValidationError) as error:
            product.full_clean()

        self.assertIn("shipping_weight_grams", error.exception.message_dict)

    def test_dry_goods_create_form_requires_shipping_weight(self):
        data = {
            "sku": "FM-DRY-FORM",
            "slug": "dry-goods-form",
            "name": "Đồ khô biểu mẫu",
            "category": Product.Category.DRY_GOODS,
            "description": "Sản phẩm kiểm tra",
            "price": "50000",
            "calories": "0",
            "protein": "0",
            "carbs": "0",
            "fat": "0",
        }

        form = ProductCreateForm(data=data)

        self.assertFalse(form.is_valid())
        self.assertIn("shipping_weight_grams", form.errors)

        form = ProductCreateForm(data={**data, "shipping_weight_grams": "500"})
        self.assertTrue(form.is_valid(), form.errors)

    def test_product_is_registered_with_catalog_admin_fields(self):
        product_admin = ProductAdmin(Product, AdminSite())

        self.assertIn("sku", product_admin.search_fields)
        self.assertIn("category", product_admin.list_filter)

    def test_django_admin_product_edits_are_logged(self):
        admin_user = get_user_model().objects.create_superuser(
            username="product-audit-admin",
            email="product-audit-admin@example.com",
            password="Admin-Strong-2026!",
        )
        product = Product.objects.create(
            sku="FM-AUDIT-001",
            slug="audit-product",
            name="Món ghi nhật ký",
            category=Product.Category.MEAL,
            description="Mô tả",
            price=Decimal("50000"),
            stock_quantity=8,
        )
        product.price = Decimal("55000")
        product.stock_quantity = 3
        request = RequestFactory().post("/admin/products/product/")
        request.user = admin_user

        ProductAdmin(Product, AdminSite()).save_model(
            request,
            product,
            form=None,
            change=True,
        )

        self.assertTrue(
            ProductActivity.objects.filter(
                product=product,
                action=ProductActivity.Action.PRICE_CHANGED,
                actor=admin_user,
            ).exists()
        )
        self.assertTrue(
            ProductActivity.objects.filter(
                product=product,
                action=ProductActivity.Action.INVENTORY_CHANGED,
                actor=admin_user,
            ).exists()
        )


class ProductApiTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            sku="FM-API-001",
            slug="whey-api",
            name="Whey API",
            category=Product.Category.DRINK,
            description="Thức uống giàu protein",
            price=Decimal("100000.00"),
            calories=250,
            protein=Decimal("25.50"),
            carbs=Decimal("12.00"),
            fat=Decimal("4.25"),
            ingredients="Whey protein, sữa",
            allergens="Sữa",
            serving="350 ml",
        )

    def test_product_list_includes_available_and_temporarily_unavailable_products(self):
        unavailable = Product.objects.create(
            sku="FM-API-002",
            slug="hidden-api",
            name="Món tạm hết",
            category=Product.Category.MEAL,
            description="Tạm hết món",
            price=Decimal("50000"),
            is_available=False,
        )

        response = self.client.get(reverse("products:list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 2)
        products = {item["id"]: item for item in response.json()["results"]}
        product = products["whey-api"]
        self.assertEqual(product["id"], "whey-api")
        self.assertEqual(product["price"], "100000.00")
        self.assertEqual(product["protein"], "25.50")
        self.assertEqual(product["shipping_weight_grams"], 0)
        self.assertEqual(product["expiry_date"], "")
        self.assertTrue(product["available"])
        self.assertEqual(product["image"], "")
        self.assertFalse(products[unavailable.slug]["available"])

    def test_product_detail_returns_available_product(self):
        response = self.client.get(reverse("products:detail", args=[self.product.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["sku"], "FM-API-001")
        self.assertEqual(response.json()["ingredients"], "Whey protein, sữa")

    def test_product_detail_includes_temporarily_unavailable_product(self):
        self.product.is_available = False
        self.product.save(update_fields=["is_available"])

        response = self.client.get(reverse("products:detail", args=[self.product.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["available"])

    def test_product_api_is_read_only(self):
        response = self.client.post(reverse("products:list"), data={"name": "Unauthorized"})

        self.assertEqual(response.status_code, 405)
        self.assertEqual(Product.objects.count(), 1)

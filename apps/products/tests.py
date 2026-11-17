from decimal import Decimal

from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
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

    def test_only_dry_goods_retain_stock_quantity(self):
        product = Product.objects.create(
            sku="FM-FRESH-INVENTORY",
            slug="fresh-inventory-test",
            name="Salad theo đơn",
            category=Product.Category.SALAD,
            description="Được chuẩn bị sau khi đặt",
            price=Decimal("50000"),
            stock_quantity=14,
        )

        self.assertIsNone(product.stock_quantity)
        self.assertFalse(product.tracks_inventory)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Product.objects.filter(pk=product.pk).update(stock_quantity=1)

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
        self.assertIn("stock_quantity", form.errors)

        form = ProductCreateForm(
            data={
                **data,
                "shipping_weight_grams": "500",
                "stock_quantity": "6",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_fresh_product_create_form_does_not_require_or_keep_stock(self):
        form = ProductCreateForm(
            data={
                "name": "Salad làm theo đơn",
                "category": Product.Category.SALAD,
                "description": "Làm sau khi khách đặt",
                "price": "79000",
                "stock_quantity": "14",
                "calories": "320",
                "protein": "28",
                "carbs": "24",
                "fat": "9",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNone(form.cleaned_data["stock_quantity"])
        self.assertIsNone(form.save().stock_quantity)

    def test_create_form_generates_sku_and_slug_when_omitted(self):
        form = ProductCreateForm(
            data={
                "name": "Salad gà sốt mè",
                "category": Product.Category.SALAD,
                "description": "Salad tươi giàu protein",
                "price": "79000",
                "calories": "320",
                "protein": "28",
                "carbs": "24",
                "fat": "9",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        product = form.save()

        self.assertRegex(product.sku, r"^FM-[A-F0-9]{10}$")
        self.assertRegex(product.slug, r"^salad-ga-sot-me-[a-f0-9]{10}$")

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
            category=Product.Category.DRY_GOODS,
            description="Mô tả",
            price=Decimal("50000"),
            stock_quantity=8,
            shipping_weight_grams=500,
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

    def test_product_list_allows_backorders_but_respects_staff_pause(self):
        unavailable = Product.objects.create(
            sku="FM-API-002",
            slug="hidden-api",
            name="Món tạm hết",
            category=Product.Category.MEAL,
            description="Tạm hết món",
            price=Decimal("50000"),
            is_available=False,
        )
        out_of_stock = Product.objects.create(
            sku="FM-API-003",
            slug="out-of-stock-api",
            name="Món hết hàng",
            category=Product.Category.DRY_GOODS,
            description="Đã hết tồn kho",
            price=Decimal("50000"),
            stock_quantity=0,
            shipping_weight_grams=500,
        )

        response = self.client.get(reverse("products:list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 3)
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
        self.assertTrue(products[out_of_stock.slug]["available"])

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

    def test_fresh_food_availability_does_not_depend_on_inventory(self):
        self.product.stock_quantity = 0
        self.product.save(update_fields=["stock_quantity"])

        response = self.client.get(reverse("products:detail", args=[self.product.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["available"])
        self.assertIsNone(Product.objects.get(pk=self.product.pk).stock_quantity)

    def test_product_api_is_read_only(self):
        response = self.client.post(reverse("products:list"), data={"name": "Unauthorized"})

        self.assertEqual(response.status_code, 405)
        self.assertEqual(Product.objects.count(), 1)

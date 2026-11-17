from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models


class Product(models.Model):
    class Category(models.TextChoices):
        DRY_GOODS = "dry_goods", "Đồ khô"
        DRINK = "drink", "Thức uống"
        MEAL = "meal", "Bữa ăn"
        RICE = "rice", "Cơm"
        SALAD = "salad", "Salad"
        SNACK = "snack", "Ăn nhẹ"
        COMBO = "combo", "Combo"

    sku = models.CharField("Mã sản phẩm", max_length=32, unique=True)
    slug = models.SlugField("Đường dẫn", max_length=140, unique=True)
    name = models.CharField("Tên sản phẩm", max_length=120)
    category = models.CharField("Danh mục", max_length=16, choices=Category.choices)
    description = models.CharField("Mô tả", max_length=500)
    price = models.DecimalField(
        "Giá bán",
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
    )
    stock_quantity = models.PositiveIntegerField(
        "Tồn kho (đơn vị)",
        null=True,
        blank=True,
        default=None,
    )
    shipping_weight_grams = models.PositiveIntegerField(
        "Khối lượng giao hàng (g)",
        default=0,
        help_text="Bắt buộc với đồ khô; tính cả bao bì để ước tính phí vận chuyển.",
    )
    expiry_date = models.DateField("Hạn sử dụng", null=True, blank=True)
    low_stock_threshold = models.PositiveIntegerField("Ngưỡng cảnh báo", default=5)
    image = models.ImageField("Ảnh sản phẩm", upload_to="products/%Y/%m/", blank=True)
    is_available = models.BooleanField("Đang bán", default=True)
    is_featured = models.BooleanField("Sản phẩm nổi bật", default=False)
    calories = models.PositiveSmallIntegerField("Calo", default=0)
    protein = models.DecimalField(
        "Protein (g)", max_digits=6, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    carbs = models.DecimalField(
        "Carb (g)", max_digits=6, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    fat = models.DecimalField(
        "Chất béo (g)", max_digits=6, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    ingredients = models.TextField("Thành phần", blank=True)
    allergens = models.CharField("Chất gây dị ứng", max_length=250, blank=True)
    serving = models.CharField("Khẩu phần", max_length=80, blank=True)
    created_at = models.DateTimeField("Ngày tạo", auto_now_add=True)
    updated_at = models.DateTimeField("Cập nhật lần cuối", auto_now=True)

    class Meta:
        ordering = ["name", "pk"]
        verbose_name = "Sản phẩm"
        verbose_name_plural = "Sản phẩm"
        indexes = [
            models.Index(fields=["category", "is_available"]),
            models.Index(fields=["is_featured", "is_available"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(category="dry_goods")
                | models.Q(stock_quantity__isnull=True),
                name="product_inventory_only_for_dry_goods",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.sku})"

    @property
    def tracks_inventory(self):
        return self.category == self.Category.DRY_GOODS

    def clean(self):
        super().clean()
        if not self.tracks_inventory:
            self.stock_quantity = None
        if self.tracks_inventory and self.shipping_weight_grams < 1:
            raise ValidationError(
                {"shipping_weight_grams": "Đồ khô cần khai báo khối lượng giao hàng."}
            )

    def save(self, *args, **kwargs):
        if not self.tracks_inventory:
            self.stock_quantity = None
            update_fields = kwargs.get("update_fields")
            if update_fields is not None:
                kwargs["update_fields"] = set(update_fields) | {"stock_quantity"}
        super().save(*args, **kwargs)


class ProductActivity(models.Model):
    class Action(models.TextChoices):
        CREATED = "created", "Tạo món"
        PRICE_CHANGED = "price_changed", "Thay đổi giá"
        INVENTORY_CHANGED = "inventory_changed", "Thay đổi tồn kho"
        AVAILABILITY_CHANGED = "availability_changed", "Thay đổi trạng thái bán"

    product = models.ForeignKey(
        Product,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="activity_logs",
    )
    product_name = models.CharField("Tên món", max_length=120)
    product_sku = models.CharField("Mã sản phẩm", max_length=32)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="product_activities",
    )
    action = models.CharField("Hoạt động", max_length=24, choices=Action.choices)
    old_value = models.CharField("Giá trị cũ", max_length=120, blank=True)
    new_value = models.CharField("Giá trị mới", max_length=120, blank=True)
    created_at = models.DateTimeField("Thời gian", auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        verbose_name = "Nhật ký sản phẩm"
        verbose_name_plural = "Nhật ký sản phẩm"
        indexes = [models.Index(fields=["action", "created_at"])]

    def __str__(self):
        return f"{self.get_action_display()}: {self.product_name}"


class InventoryRestockRequest(models.Model):
    class Status(models.TextChoices):
        STAFF_ALERT = "staff_alert", "Chờ nhân viên gửi quản lý"
        MANAGER_REVIEW = "manager_review", "Chờ quản lý bổ sung"
        FULFILLED = "fulfilled", "Đã bổ sung"
        CANCELLED = "cancelled", "Không còn đơn chờ"

    product = models.ForeignKey(
        Product,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="restock_requests",
    )
    product_name = models.CharField(max_length=120)
    product_sku = models.CharField(max_length=32)
    requested_quantity = models.PositiveIntegerField()
    available_quantity = models.PositiveIntegerField()
    attempt_count = models.PositiveIntegerField(default=1)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.STAFF_ALERT,
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="inventory_restock_requests",
    )
    fulfilled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="fulfilled_inventory_restock_requests",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    fulfilled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-updated_at", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["product"],
                condition=models.Q(
                    product__isnull=False,
                    status__in=["staff_alert", "manager_review"],
                ),
                name="products_one_open_restock_per_product",
            ),
        ]
        indexes = [models.Index(fields=["status", "updated_at"])]
        verbose_name = "Yêu cầu bổ sung tồn kho"
        verbose_name_plural = "Yêu cầu bổ sung tồn kho"

    def __str__(self):
        return f"{self.product_name} · {self.get_status_display()}"

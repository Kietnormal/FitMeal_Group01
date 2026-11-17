from uuid import uuid4

from django import forms
from django.core.exceptions import ValidationError
from django.utils.text import slugify

from .models import Product


def _new_product_identifiers(name):
    token = uuid4().hex[:10].upper()
    slug = slugify(name)[:120] or "mon-moi"
    return f"FM-{token}", f"{slug}-{token.lower()}"


class ShippingWeightFormMixin:
    def clean_shipping_weight_grams(self):
        weight = self.cleaned_data.get("shipping_weight_grams")
        if weight is None and self.instance.pk:
            return self.instance.shipping_weight_grams
        return weight or 0


class ProductCreateForm(ShippingWeightFormMixin, forms.ModelForm):
    shipping_weight_grams = forms.IntegerField(
        required=False,
        min_value=0,
        initial=0,
        label="Khối lượng giao hàng (g)",
    )
    low_stock_threshold = forms.IntegerField(
        required=False,
        min_value=0,
        initial=5,
        label="Ngưỡng cảnh báo",
    )

    class Meta:
        model = Product
        fields = (
            "sku",
            "slug",
            "name",
            "category",
            "description",
            "price",
            "stock_quantity",
            "low_stock_threshold",
            "shipping_weight_grams",
            "expiry_date",
            "image",
            "is_available",
            "is_featured",
            "calories",
            "protein",
            "carbs",
            "fat",
            "serving",
            "ingredients",
            "allergens",
        )
        widgets = {
            "description": forms.Textarea(attrs={"rows": 2}),
            "ingredients": forms.Textarea(attrs={"rows": 2}),
            "expiry_date": forms.DateInput(attrs={"type": "date"}),
            "image": forms.ClearableFileInput(attrs={"accept": "image/*"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound and not self.instance.pk:
            self.fields["category"].initial = Product.Category.MEAL
        for field_name in ("sku", "slug"):
            self.fields[field_name].required = False
            self.fields[field_name].widget = forms.HiddenInput()

    def clean_low_stock_threshold(self):
        threshold = self.cleaned_data.get("low_stock_threshold")
        return 5 if threshold is None else threshold

    def clean_stock_quantity(self):
        quantity = self.cleaned_data.get("stock_quantity")
        if self.cleaned_data.get("category") == Product.Category.DRY_GOODS:
            if quantity is None:
                raise ValidationError("Đồ khô cần nhập số lượng tồn kho.")
            return quantity
        return None

    def save(self, commit=True):
        product = super().save(commit=False)
        if not product.sku or not product.slug:
            product.sku, product.slug = _new_product_identifiers(product.name)
        if commit:
            product.save()
            self.save_m2m()
        return product


class ProductManagerUpdateForm(ShippingWeightFormMixin, forms.ModelForm):
    shipping_weight_grams = forms.IntegerField(
        required=False,
        min_value=0,
        initial=0,
        label="Khối lượng giao hàng (g)",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and not self.instance.tracks_inventory:
            self.fields.pop("stock_quantity", None)
            self.fields.pop("low_stock_threshold", None)

    class Meta:
        model = Product
        fields = (
            "price",
            "stock_quantity",
            "low_stock_threshold",
            "shipping_weight_grams",
            "expiry_date",
            "calories",
            "is_available",
        )
        labels = {
            "price": "Giá bán (đ)",
            "stock_quantity": "Tồn kho",
            "low_stock_threshold": "Ngưỡng cảnh báo",
            "shipping_weight_grams": "Khối lượng giao hàng (g)",
            "expiry_date": "Hạn sử dụng",
            "calories": "Calo (kcal)",
            "is_available": "Đang bán",
        }
        widgets = {"expiry_date": forms.DateInput(attrs={"type": "date"})}

class ProductInventoryUpdateForm(ShippingWeightFormMixin, forms.ModelForm):
    shipping_weight_grams = forms.IntegerField(
        required=False,
        min_value=0,
        initial=0,
        label="Khối lượng giao hàng (g)",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and not self.instance.tracks_inventory:
            self.fields.pop("stock_quantity", None)
            self.fields.pop("low_stock_threshold", None)

    class Meta:
        model = Product
        fields = (
            "stock_quantity",
            "low_stock_threshold",
            "shipping_weight_grams",
            "expiry_date",
        )
        labels = {
            "stock_quantity": "Tồn kho",
            "low_stock_threshold": "Ngưỡng cảnh báo",
            "shipping_weight_grams": "Khối lượng giao hàng (g)",
            "expiry_date": "Hạn sử dụng",
        }
        widgets = {"expiry_date": forms.DateInput(attrs={"type": "date"})}

class ProductQuickEditForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ("price", "is_available", "is_featured")

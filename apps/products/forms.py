from django import forms

from .models import Product


class ShippingWeightFormMixin:
    def clean_shipping_weight_grams(self):
        return self.cleaned_data.get("shipping_weight_grams") or 0


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
        }

    def clean_low_stock_threshold(self):
        threshold = self.cleaned_data.get("low_stock_threshold")
        return 5 if threshold is None else threshold

class ProductManagerUpdateForm(ShippingWeightFormMixin, forms.ModelForm):
    shipping_weight_grams = forms.IntegerField(
        required=False,
        min_value=0,
        initial=0,
        label="Khối lượng giao hàng (g)",
    )

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
            "stock_quantity": "Tồn kho (đơn vị)",
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

    class Meta:
        model = Product
        fields = (
            "stock_quantity",
            "low_stock_threshold",
            "shipping_weight_grams",
            "expiry_date",
        )
        labels = {
            "stock_quantity": "Tồn kho (đơn vị)",
            "low_stock_threshold": "Ngưỡng cảnh báo",
            "shipping_weight_grams": "Khối lượng giao hàng (g)",
            "expiry_date": "Hạn sử dụng",
        }
        widgets = {"expiry_date": forms.DateInput(attrs={"type": "date"})}

class ProductQuickEditForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ("price", "is_available", "is_featured")

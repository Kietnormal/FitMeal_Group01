from django import forms

from .models import DeliveryIssue, Order, OrderCancellationRequest


class OrderStatusUpdateForm(forms.ModelForm):
    status = forms.ChoiceField(
        label="Trạng thái",
        choices=Order.Status.choices,
        widget=forms.Select(attrs={"class": "status-select"}),
    )

    class Meta:
        model = Order
        fields = ("status",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["status"].choices = [
            (
                value,
                "Không liên lạc được với khách"
                if value == Order.Status.DELIVERY_ISSUE
                else label,
            )
            for value, label in Order.Status.choices
            if value not in {
                Order.Status.CANCELLED,
                Order.Status.DELIVERED,
            }
        ]


class CancellationReasonForm(forms.Form):
    reason = forms.CharField(
        label="Lý do",
        min_length=3,
        max_length=1000,
        strip=True,
        widget=forms.Textarea(attrs={"rows": 3, "maxlength": 1000}),
        error_messages={
            "required": "Vui lòng nhập lý do hủy.",
            "min_length": "Lý do cần có ít nhất 3 ký tự.",
        },
    )


class CancellationContactForm(forms.Form):
    outcome = forms.ChoiceField(
        choices=[
            (OrderCancellationRequest.ContactOutcome.AGREED_TO_CONTINUE, "Khách đồng ý nhận tiếp"),
            (OrderCancellationRequest.ContactOutcome.STILL_WANTS_CANCEL, "Khách vẫn muốn hủy"),
            (OrderCancellationRequest.ContactOutcome.NO_ANSWER, "Không liên lạc được"),
        ]
    )
    note = forms.CharField(
        label="Ghi chú cuộc gọi",
        min_length=2,
        max_length=1000,
        strip=True,
        widget=forms.Textarea(attrs={"rows": 2, "maxlength": 1000}),
        error_messages={
            "required": "Vui lòng ghi lại kết quả cuộc gọi.",
            "min_length": "Ghi chú cần có ít nhất 2 ký tự.",
        },
    )


class CancellationResolutionForm(forms.Form):
    decision = forms.ChoiceField(choices=[("approve", "Duyệt hủy"), ("reject", "Từ chối")])
    reason = forms.CharField(
        required=False,
        max_length=1000,
        strip=True,
        widget=forms.Textarea(attrs={"rows": 2, "maxlength": 1000}),
    )

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("decision") == "reject" and not cleaned_data.get("reason"):
            self.add_error("reason", "Vui lòng nêu lý do từ chối yêu cầu hủy.")
        return cleaned_data


class DeliveryIssueForm(forms.Form):
    details = forms.CharField(
        label="Mô tả tình trạng",
        min_length=3,
        max_length=1000,
        strip=True,
        widget=forms.Textarea(attrs={"rows": 3, "maxlength": 1000}),
        error_messages={
            "required": "Vui lòng mô tả tình trạng chưa nhận được hàng.",
            "min_length": "Mô tả cần có ít nhất 3 ký tự.",
        },
    )


class DeliveryIssueResolutionForm(forms.Form):
    decision = forms.ChoiceField(
        choices=[
            (DeliveryIssue.Resolution.CONFIRMED, "Xác nhận khách đã nhận hàng"),
            (DeliveryIssue.Resolution.REDELIVER, "Tiếp tục giao hàng"),
        ]
    )
    resolution = forms.CharField(
        min_length=3,
        max_length=1000,
        strip=True,
        widget=forms.Textarea(attrs={"rows": 2, "maxlength": 1000}),
        error_messages={
            "required": "Vui lòng ghi chú kết quả xử lý.",
            "min_length": "Ghi chú cần có ít nhất 3 ký tự.",
        },
    )

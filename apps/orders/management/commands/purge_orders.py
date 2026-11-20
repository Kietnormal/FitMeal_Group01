from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import OrderReview, PointsTransaction
from apps.orders.inventory import _sync_inventory_restock_request, restore_order_inventory
from apps.orders.models import (
    DeliveryIssue,
    Order,
    OrderCancellationRequest,
    OrderCareRequest,
    OrderItem,
    OrderPiiAccessLog,
)
from apps.payments.models import PaymentTransaction
from apps.products.models import Product


class Command(BaseCommand):
    help = (
        "Delete every order and the data attached to it (items, payments, reviews, "
        "care/cancellation requests, delivery issues, PII access logs) plus the reward "
        "points history. Customer, staff and product records are kept. Stock deducted "
        "for orders that were neither delivered nor cancelled is returned first. "
        "Without --yes the command only reports what would be deleted."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Actually delete. Without it nothing is changed.",
        )

    def handle(self, *args, yes=False, **options):
        counts = [
            ("Đơn hàng", Order.objects.count()),
            ("Món trong đơn", OrderItem.objects.count()),
            ("Giao dịch thanh toán", PaymentTransaction.objects.count()),
            ("Đánh giá đơn", OrderReview.objects.count()),
            ("Yêu cầu hủy đơn", OrderCancellationRequest.objects.count()),
            ("Yêu cầu chăm sóc", OrderCareRequest.objects.count()),
            ("Khiếu nại giao hàng", DeliveryIssue.objects.count()),
            ("Nhật ký xem thông tin khách", OrderPiiAccessLog.objects.count()),
            ("Lịch sử điểm thưởng", PointsTransaction.objects.count()),
        ]
        open_orders = Order.objects.exclude(
            status__in=[Order.Status.DELIVERED, Order.Status.CANCELLED]
        )
        restock_orders = open_orders.filter(items__inventory_deducted=True).distinct()

        for label, count in counts:
            self.stdout.write(f"  {label}: {count}")
        self.stdout.write(
            f"  Đơn chưa giao còn giữ tồn kho đồ khô (sẽ trả lại kho): {restock_orders.count()}"
        )

        if not yes:
            self.stdout.write(
                self.style.WARNING(
                    "Chưa xoá gì. Chạy lại với --yes để xoá vĩnh viễn các dữ liệu trên."
                )
            )
            return

        with transaction.atomic():
            for order in restock_orders:
                restore_order_inventory(order)
            PointsTransaction.objects.all().delete()
            # Deleting orders cascades to items, payments, reviews, requests, issues and logs.
            Order.objects.all().delete()
            for product in Product.objects.filter(category=Product.Category.DRY_GOODS):
                _sync_inventory_restock_request(product)

        self.stdout.write(
            self.style.SUCCESS(
                "Đã xoá toàn bộ dữ liệu mua hàng. Tài khoản khách, nhân viên và sản phẩm vẫn giữ nguyên."
            )
        )

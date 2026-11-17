from django.db import transaction
from django.db.models import Sum

from apps.products.models import InventoryRestockRequest, Product, ProductActivity
from apps.products.services import record_product_activity

from .models import Order, OrderItem


def reserve_order_inventory(order_items, *, actor):
    for item in order_items:
        product = item.product
        if (
            not product.tracks_inventory
            or product.stock_quantity is None
            or product.stock_quantity < item.quantity
        ):
            continue

        old_quantity = product.stock_quantity
        product.stock_quantity -= item.quantity
        item.inventory_deducted = True
        product.save(update_fields=["stock_quantity", "updated_at"])
        record_product_activity(
            product=product,
            actor=actor,
            action=ProductActivity.Action.INVENTORY_CHANGED,
            old_value=str(old_quantity),
            new_value=str(product.stock_quantity),
        )


def restore_order_inventory(order, *, actor=None):
    with transaction.atomic():
        items = list(
            OrderItem.objects.select_for_update()
            .filter(order_id=order.pk)
            .order_by("pk")
        )
        products = {
            product.pk: product
            for product in Product.objects.select_for_update()
            .filter(
                pk__in={item.product_id for item in items if item.product_id}
            )
            .order_by("pk")
        }

        for item in items:
            product = products.get(item.product_id)
            if (
                item.inventory_deducted
                and product
                and product.tracks_inventory
                and product.stock_quantity is not None
            ):
                old_quantity = product.stock_quantity
                product.stock_quantity += item.quantity
                product.save(update_fields=["stock_quantity", "updated_at"])
                record_product_activity(
                    product=product,
                    actor=actor,
                    action=ProductActivity.Action.INVENTORY_CHANGED,
                    old_value=str(old_quantity),
                    new_value=str(product.stock_quantity),
                )

        if items:
            for item in items:
                item.inventory_deducted = False
            OrderItem.objects.bulk_update(items, ["inventory_deducted"])
        for product in products.values():
            _sync_inventory_restock_request(product)


def _pending_backorder_items(product):
    active_orders = Order.objects.exclude(
        status__in=[Order.Status.DELIVERED, Order.Status.CANCELLED]
    ).values("pk")
    return OrderItem.objects.filter(
        product=product,
        product_category=Product.Category.DRY_GOODS,
        inventory_deducted=False,
        order_id__in=active_orders,
    )


def _pending_backorder_quantity(product):
    return _pending_backorder_items(product).aggregate(total=Sum("quantity"))["total"] or 0


def _sync_inventory_restock_request(product):
    request = InventoryRestockRequest.objects.select_for_update().filter(
        product=product,
        status__in=[
            InventoryRestockRequest.Status.STAFF_ALERT,
            InventoryRestockRequest.Status.MANAGER_REVIEW,
        ],
    ).first()
    if not request:
        return
    requested_quantity = _pending_backorder_quantity(product)
    if requested_quantity == 0:
        request.status = InventoryRestockRequest.Status.CANCELLED
    request.requested_quantity = requested_quantity
    request.available_quantity = product.stock_quantity or 0
    request.save(
        update_fields=[
            "status",
            "requested_quantity",
            "available_quantity",
            "updated_at",
        ]
    )


def record_inventory_shortage(product):
    requested_quantity = _pending_backorder_quantity(product)
    return InventoryRestockRequest.objects.create(
        product=product,
        product_name=product.name,
        product_sku=product.sku,
        requested_quantity=requested_quantity,
        available_quantity=product.stock_quantity or 0,
    )


def update_inventory_shortage(product):
    request = InventoryRestockRequest.objects.select_for_update().filter(
        product=product,
        status__in=[
            InventoryRestockRequest.Status.STAFF_ALERT,
            InventoryRestockRequest.Status.MANAGER_REVIEW,
        ],
    ).first()
    if request:
        request.requested_quantity = _pending_backorder_quantity(product)
        request.available_quantity = product.stock_quantity or 0
        request.attempt_count += 1
        request.save(
            update_fields=[
                "requested_quantity",
                "available_quantity",
                "attempt_count",
                "updated_at",
            ]
        )
        return request
    return record_inventory_shortage(product)




def fulfill_inventory_backorders(product_id, *, actor):
    active_orders = Order.objects.exclude(
        status__in=[Order.Status.DELIVERED, Order.Status.CANCELLED]
    ).values("pk")
    items = list(
        OrderItem.objects.select_for_update()
        .filter(
            product_id=product_id,
            product_category=Product.Category.DRY_GOODS,
            inventory_deducted=False,
            order_id__in=active_orders,
        )
        .order_by("order_id", "pk")
    )
    product = Product.objects.select_for_update().get(pk=product_id)
    requested_quantity = sum(item.quantity for item in items)
    if (
        not requested_quantity
        or product.stock_quantity is None
        or product.stock_quantity < requested_quantity
    ):
        return product, requested_quantity, False

    old_quantity = product.stock_quantity
    product.stock_quantity -= requested_quantity
    product.save(update_fields=["stock_quantity", "updated_at"])
    for item in items:
        item.inventory_deducted = True
    OrderItem.objects.bulk_update(items, ["inventory_deducted"])
    record_product_activity(
        product=product,
        actor=actor,
        action=ProductActivity.Action.INVENTORY_CHANGED,
        old_value=str(old_quantity),
        new_value=str(product.stock_quantity),
    )
    return product, requested_quantity, True

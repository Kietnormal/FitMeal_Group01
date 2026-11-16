from .models import ProductActivity


def record_product_activity(*, product, actor, action, old_value="", new_value=""):
    return ProductActivity.objects.create(
        product=product,
        product_name=product.name,
        product_sku=product.sku,
        actor=actor,
        action=action,
        old_value=old_value,
        new_value=new_value,
    )

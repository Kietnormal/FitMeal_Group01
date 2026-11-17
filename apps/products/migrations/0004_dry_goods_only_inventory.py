from django.db import migrations, models


def clear_fresh_product_stock(apps, schema_editor):
    Product = apps.get_model("products", "Product")
    Product.objects.exclude(category="dry_goods").update(stock_quantity=None)


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0003_product_expiry_date_product_shipping_weight_grams_and_more"),
    ]

    operations = [
        migrations.RunPython(clear_fresh_product_stock, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="product",
            constraint=models.CheckConstraint(
                condition=models.Q(category="dry_goods")
                | models.Q(stock_quantity__isnull=True),
                name="product_inventory_only_for_dry_goods",
            ),
        ),
    ]

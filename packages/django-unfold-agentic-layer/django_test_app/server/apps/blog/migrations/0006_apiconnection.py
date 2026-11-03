from django.db import migrations, models

import server.apps.blog.models


class Migration(migrations.Migration):
    dependencies = [
        ("blog", "0005_usagepackage"),
    ]

    operations = [
        migrations.CreateModel(
            name="ApiConnection",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("name", models.CharField(max_length=255)),
                ("access_token", server.apps.blog.models.SecretCharField(max_length=255)),
            ],
        ),
    ]

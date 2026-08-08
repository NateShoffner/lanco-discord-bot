from tortoise import fields
from tortoise.models import Model


class Bar(Model):
    id = fields.IntField(primary_key=True)
    bar_name = fields.CharField(max_length=255)
    address = fields.CharField(max_length=255)
    latitude = fields.FloatField()
    longitude = fields.FloatField()
    rating = fields.FloatField(null=True)
    price_level = fields.IntField(null=True)
    business_status = fields.CharField(max_length=255, null=True)
    place_id = fields.CharField(max_length=255)

    class Meta:
        table = "bars"

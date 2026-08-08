from tortoise import fields
from tortoise.models import Model


class AIPromptConfig(Model):
    id = fields.IntField(primary_key=True)
    guild_id = fields.IntField()
    name = fields.CharField(max_length=255)
    prompt = fields.CharField(max_length=255)

    class Meta:
        table = "ai_prompt_config"
        unique_together = (("guild_id", "name"),)

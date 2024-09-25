from db import BaseModel
from peewee import *


class AIPromptConfig(BaseModel):
    guild_id = IntegerField()
    name = CharField()
    prompt = CharField()

    class Meta:
        table_name = "ai_prompt_config"
        primary_key = CompositeKey("guild_id", "name")

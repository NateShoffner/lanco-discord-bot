from enum import Enum

from peewee import *

database_proxy = DatabaseProxy()


class DatabaseType(Enum):
    SQLITE = "sqlite"
    MYSQL = "mysql"

    @classmethod
    def from_str(cls, value: str) -> "DatabaseType":
        try:
            return cls(value.lower())
        except ValueError:
            raise ValueError(f"Unsupported database type: {value}")


class BaseModel(Model):
    class Meta:
        database = database_proxy

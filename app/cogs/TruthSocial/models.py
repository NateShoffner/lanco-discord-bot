from db import BaseModel
from peewee import *


class TruthSocialEmbedConfig(BaseModel):
    guild_id = BigIntegerField(primary_key=True)
    enabled = BooleanField(default=False)


from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel
from utils.markdown_utils import html_to_markdown


class UserModel(BaseModel):
    id: str
    username: str
    acct: str
    display_name: str
    locked: bool
    bot: bool
    group: bool
    created_at: datetime
    note: str
    url: str
    avatar: str
    avatar_static: str
    header: str
    header_static: str
    followers_count: int
    following_count: int
    statuses_count: int
    last_status_at: str
    verified: bool
    location: str
    website: str

    # note needs to be converted from HTML to markdown
    def markdown_note(self):
        return html_to_markdown(self.note)


class MetaData(BaseModel):
    aspect: float
    height: int
    size: str
    width: int


class Meta(BaseModel):
    original: MetaData
    small: MetaData


class MediaAttachment(BaseModel):
    id: str
    type: str
    url: str
    preview_url: str
    external_video_id: Any
    remote_url: Any
    preview_remote_url: Any
    text_url: Any
    meta: Meta
    description: Optional[str]
    blurhash: str
    processing: str


class StatusModel(BaseModel):
    id: str
    created_at: datetime
    sensitive: bool
    spoiler_text: str
    visibility: str
    uri: str
    url: str
    content: str
    account: UserModel
    media_attachments: list[MediaAttachment]
    sponsored: bool
    replies_count: int
    reblogs_count: int
    favourites_count: int
    upvotes_count: int
    downvotes_count: int
    favourited: bool
    reblogged: bool
    muted: bool
    pinned: bool
    bookmarked: bool
    votable: bool
    edited_at: Any
    version: str
    editable: bool

    def markdown_content(self):
        return html_to_markdown(self.content)

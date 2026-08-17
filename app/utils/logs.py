"""Log handlers, including ECS-formatted JSON output for Elastic ingestion.

The console and the human-readable log file are unchanged; this adds a second
file written as ECS JSON, one document per line, for a shipper to tail into
Elasticsearch. Two files rather than one because the formats serve different
readers, and turning ``logfile.log`` into JSON would make `docker logs` and a
tail over SSH unreadable.

``ecs_logging`` picks up ``trace.id`` and ``transaction.id`` from the APM agent
by itself whenever a transaction is in flight, which is what lets Kibana jump
from a log line to the command that produced it. It only does so *during* a
transaction, so the service fields are supplied statically as well: without
them a line logged at startup or from a background task belongs to no service
at all.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
from logging.handlers import TimedRotatingFileHandler
from typing import Optional

import ecs_logging
from utils import env
from utils.dist_utils import get_service_version

logger = logging.getLogger(__name__)

DEFAULT_SERVICE_NAME = "lanco-bot"


class WinTimedRotatingFileHandler(TimedRotatingFileHandler):
    def doRollover(self):
        if self.stream:
            self.stream.close()
            self.stream = None
        super().doRollover()

    def rotate(self, source, dest):
        shutil.copy2(source, dest)
        open(source, "w").close()  # truncate in place instead of renaming


def _set_default(doc: dict, path: list[str], value) -> None:
    """Set a dotted ECS field only where nothing has claimed it."""
    for key in path[:-1]:
        nxt = doc.setdefault(key, {})
        if not isinstance(nxt, dict):
            return  # something scalar already owns this branch
        doc = nxt
    doc.setdefault(path[-1], value)


class ServiceFieldFormatter(ecs_logging.StdlibFormatter):
    """ECS formatter that fills in service fields without fighting the agent.

    Passing these through the base class's ``extra`` is not safe. When an APM
    transaction is active the agent contributes ``service.name`` of its own,
    and ``extra`` is merged strictly: two different values for one key raise
    inside ``format()``, the handler swallows it, and the line is dropped. That
    fails silently and empties the log exactly when APM is working.

    Merging afterwards with setdefault inverts the precedence. Whatever the
    agent supplied wins, these only fill the gaps, and a mismatch is impossible.
    """

    def __init__(self, fields: dict, **kwargs):
        super().__init__(**kwargs)
        self._fields = fields

    def format_to_ecs(self, record: logging.LogRecord) -> dict:
        doc = super().format_to_ecs(record)
        for dotted, value in self._fields.items():
            _set_default(doc, dotted.split("."), value)
        return doc


def _slug(value: str, fallback: str) -> str:
    """A single segment of a data stream name.

    ``logs-<dataset>-<namespace>`` is split on hyphens, so neither segment may
    contain one or the name parses into the wrong pieces.
    """
    cleaned = re.sub(r"[^a-z0-9_]+", "_", value.lower()).strip("_")
    return cleaned or fallback


def dataset_for(service_name: str) -> str:
    """The ``event.dataset`` for a service name."""
    return f"{_slug(service_name, 'bot')}.log"


def namespace_for(environment: str) -> str:
    """The data stream namespace for an environment."""
    return _slug(environment, "default")


def service_fields() -> dict:
    """Fields tying every log line to this service, deployment, and build.

    ``event.dataset`` is what the APM UI's Logs tab correlates on, so a line
    without it will not surface next to the service it came from.

    The ``data_stream.*`` trio is what the shipper routes on, keeping dev and
    prod logs in separate data streams the way the APM environment already
    separates their traces. All three are sent, not just the namespace: they
    are ``constant_keyword`` in the index template, and one that no document
    ever supplies stays valueless, so every query filtering on it silently
    matches nothing.

    The namespace is derived rather than reusing ``service.environment``
    directly, because that field has to match what the APM agent reports
    verbatim for correlation to work, and the namespace has to survive being a
    hyphen-delimited path segment. For "dev" and "prod" they are the same
    string; for "pre-prod" they are not.
    """
    name = os.getenv("ELASTIC_APM_SERVICE_NAME", DEFAULT_SERVICE_NAME)
    environment = env.current()
    dataset = dataset_for(name)
    return {
        "service.name": name,
        "service.version": get_service_version(),
        "service.environment": environment,
        "event.dataset": dataset,
        "data_stream.type": "logs",
        "data_stream.dataset": dataset,
        "data_stream.namespace": namespace_for(environment),
    }


def add_ecs_file_handler(root: logging.Logger) -> Optional[logging.Handler]:
    """Attach the ECS JSON handler if ECS_LOG_FILE names a path.

    Off unless configured: the file is only useful to a deployment that runs a
    shipper, and writing it everywhere would double log disk for everyone else.
    """
    path = os.getenv("ECS_LOG_FILE", "").strip()
    if not path:
        return None

    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    handler = WinTimedRotatingFileHandler(
        filename=path, when="midnight", interval=1, encoding="utf-8"
    )
    handler.setFormatter(ServiceFieldFormatter(service_fields()))
    root.addHandler(handler)
    logger.info(f"ECS log output enabled: {path}")
    return handler

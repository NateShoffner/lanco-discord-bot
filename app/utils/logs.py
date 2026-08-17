"""Log handlers, including ECS-formatted JSON output for Elastic ingestion.

The console and the human-readable log file are unchanged; this adds a second
file written as ECS JSON, one document per line, for a shipper to tail into
Elasticsearch. Two files rather than one because the formats serve different
readers, and turning ``logfile.log`` into JSON would make `docker logs` and a
tail over SSH unreadable.

``ecs_logging`` adds ``trace.id`` and ``transaction.id`` from the APM agent by
itself, which is what lets Kibana jump from a log line to the command that
produced it. It only does so during a transaction, so the service and routing
fields are supplied here too.
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
#: Daily ECS files kept on disk. Elasticsearch is the durable copy.
DEFAULT_RETENTION_DAYS = 7


def rotate_by_copy() -> bool:
    """Windows refuses to rename a file another handle still has open."""
    return os.name == "nt"


class WinTimedRotatingFileHandler(TimedRotatingFileHandler):
    """Daily rotation that survives Windows without hurting log shipping.

    Renaming keeps the inode, so a shipper mid-file finishes the rotated copy
    and then picks up the new one; copy-and-truncate loses whatever it had not
    reached. The workaround is confined to Windows, which is dev only.
    """

    def doRollover(self):
        if self.stream:
            self.stream.close()
            self.stream = None
        super().doRollover()

    def rotate(self, source, dest):
        if not rotate_by_copy():
            super().rotate(source, dest)
            return
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

    ``event.dataset`` is what the APM UI's Logs tab correlates on. The
    ``data_stream.*`` trio is what the shipper routes on, keeping dev and prod
    logs apart the way the APM environment already separates their traces. All
    three go out, not just the namespace: they are ``constant_keyword``, and
    one no document ever supplies stays valueless, so queries filtering on it
    match nothing.

    The namespace is derived rather than reusing ``service.environment``,
    which has to match the APM agent verbatim for correlation to work while
    the namespace has to survive being a hyphen-delimited path segment.
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


def retention_days() -> int:
    """Daily ECS files to keep, from ECS_LOG_RETENTION_DAYS.

    Bounded by default, unlike ``logfile.log``, which passes no ``backupCount``
    and so keeps every daily file forever. That is survivable for a log a human
    occasionally greps, but this one is a second copy of the same output whose
    durable home is Elasticsearch: once a shipper has read it the local file has
    no further purpose. 0 restores the keep-everything behaviour.
    """
    raw = os.getenv("ECS_LOG_RETENTION_DAYS", "").strip()
    if not raw:
        return DEFAULT_RETENTION_DAYS
    try:
        return max(0, int(raw))
    except ValueError:
        logger.warning(
            f"Ignoring invalid ECS_LOG_RETENTION_DAYS={raw!r}, "
            f"using {DEFAULT_RETENTION_DAYS}"
        )
        return DEFAULT_RETENTION_DAYS


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

    days = retention_days()
    handler = WinTimedRotatingFileHandler(
        filename=path,
        when="midnight",
        interval=1,
        backupCount=days,
        encoding="utf-8",
    )
    handler.setFormatter(ServiceFieldFormatter(service_fields()))
    root.addHandler(handler)
    kept = f"{days} day(s) kept" if days else "kept indefinitely"
    logger.info(f"ECS log output enabled: {path} ({kept})")
    return handler

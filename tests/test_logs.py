"""Tests for ECS log output.

The point of shipping logs to Elastic rather than leaving them on Logtail is
correlation: a log line has to carry enough to be attributed to this service
and, when one is in flight, to the exact transaction that produced it. These
tests pin the fields Kibana correlates on, since a missing one degrades
silently into logs that simply never appear next to the service.
"""

import json
import logging
import os
import sys

import elasticapm
import pytest
from elasticapm.base import set_client

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from utils import logs


@pytest.fixture
def ecs_log(tmp_path, monkeypatch):
    """A root-ish logger with the ECS handler attached, plus its output."""
    path = tmp_path / "ecs.json"
    monkeypatch.setenv("ECS_LOG_FILE", str(path))
    monkeypatch.setenv("BOT_ENV", "prod")
    monkeypatch.setenv("ELASTIC_APM_SERVICE_NAME", "lanco-bot")

    log = logging.getLogger("EcsTestCog")
    log.setLevel(logging.DEBUG)
    log.propagate = False
    handler = logs.add_ecs_file_handler(log)
    assert handler is not None

    def read():
        handler.flush()
        return [json.loads(line) for line in path.read_text("utf-8").splitlines()]

    yield log, read

    handler.close()
    log.removeHandler(handler)


def test_disabled_without_a_configured_path(monkeypatch):
    monkeypatch.delenv("ECS_LOG_FILE", raising=False)
    log = logging.getLogger("EcsOff")
    before = len(log.handlers)

    assert logs.add_ecs_file_handler(log) is None
    assert len(log.handlers) == before


def test_writes_one_ecs_document_per_line(ecs_log):
    log, read = ecs_log
    log.info("first")
    log.info("second")

    docs = read()
    assert len(docs) == 2
    assert docs[0]["message"] == "first"
    assert docs[0]["log.level"] == "info"
    assert docs[0]["log"]["logger"] == "EcsTestCog"
    assert "ecs.version" in docs[0]


def test_service_fields_are_present_without_a_transaction(ecs_log):
    """The gap ecs_logging leaves: it only adds service fields from an active
    APM transaction, so startup and background-task lines would have none."""
    log, read = ecs_log
    log.info("no transaction here")

    service = read()[0]["service"]
    assert service["name"] == "lanco-bot"
    assert service["environment"] == "prod"
    assert service["version"]  # version+commit of the running build


def test_event_dataset_is_set(ecs_log):
    """What the APM UI's Logs tab correlates on."""
    log, read = ecs_log
    log.info("anything")

    # Hyphen normalized: it would otherwise split the data stream name.
    assert read()[0]["event"]["dataset"] == "lanco_bot.log"


@pytest.fixture
def apm_client():
    """A client that records nothing and talks to no server."""
    client = elasticapm.Client(
        service_name="lanco-bot",
        environment="prod",
        transport_class="elasticapm.transport.base.Transport",
        disable_send=True,
        central_config="false",
        metrics_interval="0ms",
    )
    yield client
    client.close()
    set_client(None)


def test_trace_ids_link_a_line_to_its_transaction(ecs_log, apm_client):
    log, read = ecs_log

    apm_client.begin_transaction("command")
    log.warning("inside")
    apm_client.end_transaction("weather", "success")
    log.warning("outside")

    inside, outside = read()
    assert inside["trace"]["id"]
    assert inside["transaction"]["id"]
    # Correlation is per-transaction; a line outside one has nothing to link to.
    assert "transaction" not in outside


def test_agent_supplied_fields_do_not_collide_with_ours(ecs_log, apm_client):
    """Regression: passing these via the base formatter's `extra` made every
    line raise inside format() and be dropped whenever APM was active, which
    emptied the log precisely when the correlation was working."""
    log, read = ecs_log

    apm_client.begin_transaction("command")
    log.warning("during a transaction")
    apm_client.end_transaction("weather", "success")

    docs = read()
    assert len(docs) == 1, "the line was dropped by a formatter error"
    doc = docs[0]
    assert doc["message"] == "during a transaction"
    # The agent owns name and environment; ours only fill what it left out.
    assert doc["service"]["name"] == "lanco-bot"
    assert doc["service"]["environment"] == "prod"
    assert doc["service"]["version"]
    assert doc["event"]["dataset"] == "lanco_bot.log"


def test_a_disagreeing_agent_does_not_drop_the_line(ecs_log):
    """A deployment may set ELASTIC_APM_ENVIRONMENT differently from BOT_ENV,
    or ELASTIC_APM_SERVICE_NAME differently again. Whichever value ends up
    winning, the disagreement must not cost us the log line."""
    log, read = ecs_log

    client = elasticapm.Client(
        service_name="something-else",
        environment="staging",
        transport_class="elasticapm.transport.base.Transport",
        disable_send=True,
        central_config="false",
        metrics_interval="0ms",
    )
    try:
        client.begin_transaction("command")
        log.warning("mismatched")
        client.end_transaction("weather", "success")
    finally:
        client.close()
        set_client(None)

    docs = read()
    assert len(docs) == 1, "a field disagreement dropped the line"
    service = docs[0]["service"]
    assert service["name"] and service["environment"]
    assert service["version"]
    assert docs[0]["event"]["dataset"]


def test_exceptions_carry_type_and_stack_trace(ecs_log):
    log, read = ecs_log
    try:
        raise ValueError("boom")
    except ValueError:
        log.exception("it broke")

    error = read()[0]["error"]
    assert error["type"] == "ValueError"
    assert error["message"] == "boom"
    assert "raise ValueError" in error["stack_trace"]


def test_dataset_names_are_data_stream_safe():
    """`logs-<dataset>-<namespace>` splits on hyphens, so the dataset cannot
    contain one or the document routes somewhere unintended."""
    assert logs.dataset_for("lanco-bot") == "lanco_bot.log"
    assert logs.dataset_for("Lanco Bot!") == "lanco_bot.log"
    assert logs.dataset_for("") == "bot.log"


def test_service_fields_follow_the_environment(monkeypatch):
    monkeypatch.setenv("BOT_ENV", "dev")
    monkeypatch.setenv("ELASTIC_APM_SERVICE_NAME", "lanco-bot-dev")

    fields = logs.service_fields()

    assert fields["service.environment"] == "dev"
    assert fields["service.name"] == "lanco-bot-dev"
    assert fields["event.dataset"] == "lanco_bot_dev.log"

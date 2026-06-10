from contextlib import asynccontextmanager

import elasticapm


@asynccontextmanager
async def transaction(name: str, tx_type: str, **labels):
    """Async context manager that wraps a block in an APM transaction.

    Usage:
        async with apm_transaction("my_command", "custom_command"):
            ...
    """
    client = elasticapm.get_client()
    if client is None:
        yield
        return
    client.begin_transaction(tx_type)
    if labels:
        elasticapm.label(**{k: str(v) for k, v in labels.items() if v is not None})
    try:
        yield
        client.end_transaction(name, "success")
    except Exception:
        client.end_transaction(name, "failure")
        raise

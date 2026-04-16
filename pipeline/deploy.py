"""Register and serve all BetterSite flows.

This is the entrypoint for the Railway "worker" service. It:

1. Builds a ``Deployment`` for every flow we want runnable on the server.
2. Calls ``prefect.serve(...)`` which upserts the deployments (idempotent by
   name) and then blocks, polling the server for scheduled or manually
   triggered runs. Runs execute **in-process** on this service.

There is no separate work pool and no ``prefect worker`` process. Scaling is
done by running more replicas of this service.

Run locally (only when no Railway worker is live — otherwise they race):

    python -m pipeline.deploy
"""

from __future__ import annotations

import os

# Teach Prefect to capture logs emitted by our own ``pipeline.*`` loggers, not
# just ``prefect.*``. Must be set BEFORE any ``prefect`` import because Prefect
# reads its logging config once at import time.
os.environ.setdefault("PREFECT_LOGGING_EXTRA_LOGGERS", "pipeline")

from prefect import serve  # noqa: E402

from pipeline.flows.lead_generator import generate_leads  # noqa: E402
from pipeline.flows.lead_generator_batch import generate_leads_batch  # noqa: E402
from pipeline.flows.scanner import scan_sites  # noqa: E402
from pipeline.observability import configure as configure_logging  # noqa: E402


def main() -> None:
    configure_logging()

    lead_generation = generate_leads.to_deployment(
        name="lead-generation",
        parameters={
            "source": "bbb",
            "vertical": "movers",
            "state": "TX",
            "city": "Houston",
            "max_pages": None,
        },
    )

    lead_generation_batch = generate_leads_batch.to_deployment(
        name="lead-generation-batch",
        parameters={
            "source": "bbb",
            "targets_csv": "pipeline/targets/movers_us.csv",
            "max_pages_per_city": None,
            "abort_on_repeated_block": 2,
        },
    )

    site_scan = scan_sites.to_deployment(
        name="site-scan",
        parameters={"urls": None, "limit": 50},
    )

    serve(lead_generation, lead_generation_batch, site_scan)


if __name__ == "__main__":
    main()

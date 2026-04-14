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

from prefect import serve

from pipeline.flows.lead_generator import generate_leads


def main() -> None:
    lead_generation = generate_leads.to_deployment(
        name="lead-generation",
        parameters={"vertical": "movers", "city": "Austin", "country": "US", "limit": 10},
    )

    serve(lead_generation)


if __name__ == "__main__":
    main()

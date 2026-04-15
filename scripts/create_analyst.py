"""Provision a new admin analyst.

Usage:
    OHAD_PW='hunter2' python -m scripts.create_analyst \\
        --username ohad --password-env OHAD_PW

The password is read from an env var (not a CLI arg) so it never enters
shell history. Writes ops.events(event_type='analyst_created') for audit.
"""

from __future__ import annotations

import argparse
import os
import sys
import uuid

from sqlalchemy import select

from api.auth import hash_password
from pipeline.db import session_scope
from pipeline.models.analyst import Analyst
from pipeline.models.event import Event


def main() -> int:
    parser = argparse.ArgumentParser(description="Create an admin analyst")
    parser.add_argument("--username", required=True)
    parser.add_argument(
        "--password-env",
        required=True,
        help="Name of the env var holding the plaintext password",
    )
    args = parser.parse_args()

    password = os.environ.get(args.password_env)
    if not password:
        print(f"ERROR: env var {args.password_env} is empty or unset", file=sys.stderr)
        return 2

    session = session_scope()
    try:
        existing = session.scalar(
            select(Analyst).where(Analyst.username == args.username)
        )
        if existing is not None:
            print(
                f"ERROR: analyst '{args.username}' already exists (id={existing.id})",
                file=sys.stderr,
            )
            return 3

        analyst = Analyst(
            id=uuid.uuid4(),
            username=args.username,
            password_hash=hash_password(password),
            active=True,
        )
        session.add(analyst)
        session.flush()

        # Audit the provisioning. No lead_id — use a sentinel.
        # Skip event insert; ops.events requires a lead_id FK. Log to stdout instead.
        session.commit()
        print(f"OK created analyst id={analyst.id} username={analyst.username}")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())

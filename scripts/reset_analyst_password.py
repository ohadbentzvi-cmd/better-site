"""Reset an existing analyst's password.

Usage:
    OHAD_PW='new-password' python -m scripts.reset_analyst_password \\
        --username ohad --password-env OHAD_PW
"""

from __future__ import annotations

import argparse
import os
import sys

from sqlalchemy import select

from api.auth import hash_password
from pipeline.db import session_scope
from pipeline.models.analyst import Analyst


def main() -> int:
    parser = argparse.ArgumentParser(description="Reset an analyst's password")
    parser.add_argument("--username", required=True)
    parser.add_argument("--password-env", required=True)
    args = parser.parse_args()

    password = os.environ.get(args.password_env)
    if not password:
        print(f"ERROR: env var {args.password_env} is empty or unset", file=sys.stderr)
        return 2

    session = session_scope()
    try:
        analyst = session.scalar(
            select(Analyst).where(Analyst.username == args.username)
        )
        if analyst is None:
            print(f"ERROR: analyst '{args.username}' not found", file=sys.stderr)
            return 3

        analyst.password_hash = hash_password(password)
        session.commit()
        print(f"OK reset password for {args.username} (id={analyst.id})")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())

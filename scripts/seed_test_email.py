"""Deliverability seed-test script.

Sends an identical cold-email template to a hardcoded list of inboxes we
own across Gmail, Outlook, Yahoo, and Apple Mail. Run manually before every
real batch to verify the email is landing in inbox (not spam / promotions).

See docs/deliverability.md for the full seed-test protocol.

Phase 5/6 implementation TODO.
"""

from __future__ import annotations

import sys


def main() -> int:
    print("[TODO] deliverability seed test not yet implemented")
    return 0


if __name__ == "__main__":
    sys.exit(main())

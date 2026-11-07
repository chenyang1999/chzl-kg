"""Conservative outer retry policy; not a token or process budget."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re


@dataclass(frozen=True)
class Decision:
    action: str
    reason: str


def decide(returncode: int, delivery_ok: bool, text: str) -> Decision:
    # Validated current-attempt delivery, not prose matching, is authoritative.
    if returncode == 0 and delivery_ok:
        return Decision("success", "delivered")
    # Only explicit error records justify a retry. Unrecognised formats stop.
    records = "\n".join(
        line for line in text.splitlines()
        if re.match(r"^\s*(?:ERROR\b|FATAL\b|\[(?:ERROR|FATAL)\])", line, re.I)
    ).lower()
    if any(x in records for x in (
        "insufficient_quota", "usage quota", "quota exhausted",
        "accountoverdueerror", "billing limit",
    )):
        return Decision("stop", "quota")
    if re.search(r"\b(?:401|403)\b", records) or any(
        x in records for x in ("unauthorized", "invalid api key", "authentication failed")
    ):
        return Decision("stop", "authentication")
    if re.search(r"\b400\b", records) or "invalid request" in records:
        return Decision("stop", "invalid_request")
    if re.search(r"\b429\b", records) or any(
        x in records for x in ("transport timeout", "connection reset", "connection refused")
    ):
        return Decision("retry", "transient")
    return Decision("stop", "delivery_contract" if returncode == 0 else "unknown_failure")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--returncode", type=int, required=True)
    parser.add_argument("--delivery-ok", type=int, choices=(0, 1), required=True)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--offset", type=int, required=True)
    args = parser.parse_args()
    with args.log.open("rb") as stream:
        size = stream.seek(0, 2)
        if args.offset < 0 or args.offset > size:
            raise ValueError("invalid attempt log offset")
        stream.seek(args.offset)
        text = stream.read().decode("utf-8", errors="replace")
    result = decide(args.returncode, bool(args.delivery_ok), text)
    print(result.reason)
    return {"success": 0, "retry": 10, "stop": 20}[result.action]


if __name__ == "__main__":
    raise SystemExit(main())

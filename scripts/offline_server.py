"""Test-only, process-scoped outbound Python socket/DNS denial. No OS settings changed."""

import json
import os
import socket
import sys
from pathlib import Path


def main() -> None:
    audit = Path(os.environ["APP_OFFLINE_AUDIT_LOG"])
    phase = "guard_self_test"

    def deny(event: str, args: tuple) -> None:
        if event in {"socket.connect", "socket.getaddrinfo", "socket.gethostbyname"}:
            with audit.open("a") as file:
                file.write(json.dumps({"event": event, "phase": phase}) + "\n")
            raise OSError("Outbound sockets/DNS disabled in this test process")

    sys.addaudithook(deny)
    with socket.socket() as probe:
        try:
            probe.connect(("203.0.113.1", 9))
        except OSError:
            pass
        else:
            raise RuntimeError("Offline guard failed")
    phase = "backend_runtime"
    from app.__main__ import main as serve

    serve()


if __name__ == "__main__":
    main()

"""Headless packaged backend. Its native parent supplies bootstrap over stdin."""

import json
import os
import socket
import sys
import threading
import time

_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if os.path.isdir(_SRC) and _SRC not in sys.path:
    sys.path.insert(0, _SRC)


def main() -> int:
    import uvicorn

    from rune_pilot.composition.desktop_backend import PROTOCOL_VERSION, create_desktop_app
    from rune_pilot.shared.app_meta import __version__

    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    protocol_out = sys.stdout
    # Ordinary application diagnostics cannot corrupt or expose bootstrap data.
    sys.stdout = sys.stderr
    try:
        line = sys.stdin.readline(16385)
        if len(line) > 16384 or not line.endswith("\n"):
            raise ValueError("Invalid bootstrap")
        bootstrap = json.loads(line)
        token = bootstrap["token"]
        profile = bootstrap.get("profile_dir")
        if not isinstance(token, str) or (profile is not None and not isinstance(profile, str)):
            raise ValueError("Invalid bootstrap")
        app = create_desktop_app(token, profile_dir=profile)
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind(("127.0.0.1", 0))
        listener.listen(128)
        port = listener.getsockname()[1]
        server = uvicorn.Server(
            uvicorn.Config(
                app,
                host="127.0.0.1",
                port=port,
                loop="asyncio",
                http="h11",
                ws="none",
                log_level="warning",
                access_log=False,
                timeout_graceful_shutdown=12,
            )
        )

        def parent_commands() -> None:
            # Closing the parent's pipe (including a parent crash) stops automation.
            for command in sys.stdin:
                try:
                    if json.loads(command).get("command") == "shutdown":
                        break
                except (ValueError, AttributeError):
                    break
            server.should_exit = True

        def ready() -> None:
            deadline = time.monotonic() + 50
            while not server.started and not server.should_exit:
                if time.monotonic() >= deadline:
                    server.should_exit = True
                    return
                time.sleep(0.025)
            if server.started and not server.should_exit:
                protocol_out.write(
                    json.dumps(
                        {
                            "event": "ready",
                            "protocol": PROTOCOL_VERSION,
                            "version": __version__,
                            "port": port,
                        }
                    )
                    + "\n"
                )
                protocol_out.flush()

        threading.Thread(target=parent_commands, daemon=True).start()
        threading.Thread(target=ready, daemon=True).start()
        try:
            server.run(sockets=[listener])
        finally:
            listener.close()
        return 0 if server.started else 1
    except Exception:
        # Do not echo stdin, session keys or exception payloads into launch errors.
        print(
            "RunePilot backend could not start. Check profile access and packaged resources.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

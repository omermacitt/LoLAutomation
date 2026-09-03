"""
Quick test for the Riot Client HTTP API auto-login.

Usage (Riot Client must already be running and on the login screen):

    python test_login.py                        # just checks lockfile + connectivity
    python test_login.py <username> <password>  # full login attempt
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from src.rune_pilot.infrastructure.riot_client import (
    is_riot_client_running,
    _find_riot_client_lockfile,
    _parse_riot_client_lockfile,
    auto_login_api,
)


def check_lockfile():
    print("=== Lockfile check ===")
    path = _find_riot_client_lockfile()
    if not path:
        print("  FAIL  Lockfile not found.")
        print("        Make sure Riot Client is running.")
        return False

    print(f"  OK    Found: {path}")
    creds = _parse_riot_client_lockfile()
    if not creds:
        print("  FAIL  Could not parse lockfile.")
        return False

    port, pw = creds
    print(f"  OK    port={port}  password={'*' * len(pw)}")
    return True


def check_connectivity(port: int, password: str):
    print("\n=== Connectivity check ===")
    import base64, requests, urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    auth = base64.b64encode(f"riot:{password}".encode()).decode()
    url = f"https://127.0.0.1:{port}/rso-auth/v1/authorization"
    try:
        resp = requests.get(url, headers={"Authorization": f"Basic {auth}"}, verify=False, timeout=5)
        print(f"  OK    GET {url} -> {resp.status_code}")
        print(f"        body: {resp.text[:200]}")
        return True
    except Exception as e:
        print(f"  FAIL  {e}")
        return False


def do_login(username: str, password: str):
    print(f"\n=== Login attempt: {username} ===")
    result = auto_login_api(username, password, timeout=15)
    t = result.get("type")
    if t == "response":
        print(f"  OK    Login accepted — {result.get('message', '')}")
    elif t == "auth_failure":
        print("  FAIL  Wrong username or password.")
    elif t == "multifactor":
        print("  INFO  2FA required — complete it in Riot Client manually.")
    else:
        print(f"  ERROR type={t!r}  message={result.get('message', '')}")


if __name__ == "__main__":
    print(f"Riot Client running: {is_riot_client_running()}\n")

    ok = check_lockfile()
    if ok:
        creds = _parse_riot_client_lockfile()
        if creds:
            check_connectivity(creds[0], creds[1])

    if len(sys.argv) == 3:
        do_login(sys.argv[1], sys.argv[2])
    elif len(sys.argv) == 2:
        print("\nUsage: python test_login.py <username> <password>")
    else:
        print("\nTip: run with username and password to test a full login:")
        print("     python test_login.py myusername mypassword")

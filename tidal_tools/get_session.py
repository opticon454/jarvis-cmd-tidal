"""Log in to TIDAL once and print the four values to enter in the app. Needs ``pip install tidalapi``.

Run it on a machine with a browser: it prints a link, you approve it, and it prints the tokens. Nothing is written to
disk. Treat the output like a password.
"""

import tidalapi


def main() -> None:
    session = tidalapi.Session()
    session.login_oauth_simple()  # prints the link to open and waits for approval
    if not session.check_login():
        raise SystemExit("TIDAL login did not complete.")
    print()
    print(f"TIDAL_TOKEN_TYPE    = {session.token_type}")
    print(f"TIDAL_ACCESS_TOKEN  = {session.access_token}")
    print(f"TIDAL_REFRESH_TOKEN = {session.refresh_token}")
    print(f"TIDAL_EXPIRY        = {session.expiry_time.isoformat()}")


if __name__ == "__main__":
    main()

import os
from secrets import compare_digest


TOKEN_ENVIRONMENT_VARIABLE = "MOODLE_WEBHOOK_TOKEN"


def get_webhook_token():
    return os.environ.get(TOKEN_ENVIRONMENT_VARIABLE, "")


def bearer_token_matches(authorization_header, expected_token):
    if not authorization_header or not expected_token:
        return False

    parts = authorization_header.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return False

    supplied_token = parts[1].strip()
    if not supplied_token:
        return False

    return compare_digest(
        supplied_token.encode("utf-8"),
        expected_token.encode("utf-8"),
    )

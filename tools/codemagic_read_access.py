"""Read only the approved Codemagic application's metadata; never start builds."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.request

APP_ID = "6ac5b7b31811e71b67b38c2a"
ENDPOINT = "https://api.codemagic.io/apps/" + APP_ID
LIMIT = 512 * 1024
REPORT = Path("artifacts/codemagic-read-access.json")


class RefusedRedirect(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        raise RefusedRedirect()


def read_application(token, opener=None):
    result = {
        "status": "NOT_AUTHENTICATED",
        "app_id": APP_ID,
        "app_id_matched": False,
        "apple_authentication_verified": False,
        "integration_resolution_verified": False,
        "signing_ready": False,
        "builds_started": 0,
        "resources_modified": False,
        "response_contents_saved": False,
    }
    if not token:
        return {**result, "status": "CODEMAGIC_TOKEN_MISSING"}
    token = token.strip()
    if not re.fullmatch(r"[!-~]{20,4096}", token):
        return {**result, "status": "CODEMAGIC_TOKEN_INVALID"}
    opener = opener or urllib.request.build_opener(NoRedirect())
    request = urllib.request.Request(ENDPOINT, method="GET", headers={
        "x-auth-token": token, "Accept": "application/json",
        "User-Agent": "AtodeYaruBox-ReadOnly-Access-Check",
    })
    try:
        with opener.open(request, timeout=20) as response:
            raw = response.read(LIMIT + 1)
        if len(raw) > LIMIT:
            return {**result, "status": "RESPONSE_LIMIT_EXCEEDED"}
        payload = json.loads(raw)
        application = payload.get("application") if isinstance(payload, dict) else None
        if not isinstance(application, dict) or application.get("_id") != APP_ID:
            return {**result, "status": "APP_RESPONSE_IDENTITY_UNVERIFIED"}
        # Never copy arbitrary server text, env values, tokens, names or emails.
        branches = application.get("branches", [])
        if not isinstance(branches, list):
            branches = []
        return {
            **result,
            "status": "APP_METADATA_READ_AUTHENTICATED",
            "app_id_matched": True,
            "team_reference_field_present": "teamId" in application,
            "team_reference_nonempty": bool(application.get("teamId")),
            "team_scope_verified": False,
            "original_work_branch_listed": "atodeyarubox-build" in branches,
            "preflight_branch_listed": "codex/apple-connection-check-2354a98" in branches,
        }
    except urllib.error.HTTPError as error:
        # HTTP error bodies/headers and exception strings may contain credentials.
        return {**result, "status": "CODEMAGIC_HTTP_ERROR", "http_status": int(error.code)}
    except RefusedRedirect:
        return {**result, "status": "AUTHENTICATED_REDIRECT_REFUSED"}
    except (urllib.error.URLError, TimeoutError, OSError):
        return {**result, "status": "CODEMAGIC_NETWORK_UNAVAILABLE"}
    except (ValueError, TypeError):
        return {**result, "status": "CODEMAGIC_RESPONSE_INVALID"}
    except Exception:
        # Unanticipated provider/transport exceptions must not print a traceback.
        return {**result, "status": "CODEMAGIC_READ_UNAVAILABLE"}


def write_report(path, result):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def main():
    # Invalidate an old success before reading credentials or making requests.
    write_report(REPORT, {"status": "NOT_RUN", "app_id": APP_ID})
    token = os.environ.pop("CODEMAGIC_API_TOKEN", "")
    result = read_application(token)
    token = ""
    result["checked_at"] = datetime.now(timezone.utc).isoformat()
    revision = os.environ.get("GITHUB_SHA", "")
    if re.fullmatch(r"[0-9a-f]{40}", revision):
        result["source_commit"] = revision
    write_report(REPORT, result)
    print(result["status"])
    return 0 if result["status"] == "APP_METADATA_READ_AUTHENTICATED" else 1


if __name__ == "__main__":
    sys.exit(main())

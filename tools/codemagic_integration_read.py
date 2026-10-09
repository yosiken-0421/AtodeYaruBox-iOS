"""Compare the approved app's owner context and saved Apple alias, read only."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import unicodedata
import urllib.error
import urllib.request

from tools.codemagic_read_access import APP_ID, NoRedirect, RefusedRedirect, write_report

BUILD_ID = "6ac90ba159e0a0dce27504a9"
ALIAS = "AtodeYaruBox-CI"
LIMIT = 1024 * 1024
REPORT = Path("artifacts/codemagic-integration-read.json")


class Unavailable(Exception):
    def __init__(self, stage, code=None):
        self.stage, self.code = stage, code


def valid_id(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{24}", value) is not None


def alias_metadata(context):
    integration = context.get("appStoreConnectIntegration")
    integration = integration if isinstance(integration, dict) else {}
    keys = integration.get("apiKeys")
    keys = keys if isinstance(keys, list) else []
    exact = [key for key in keys if isinstance(key, dict) and key.get("name") == ALIAS]
    normalized = [key for key in keys if isinstance(key, dict) and isinstance(key.get("name"), str)
                  and unicodedata.normalize("NFKC", key["name"]).strip() == ALIAS]
    return {
        "integration_field_present": "appStoreConnectIntegration" in context,
        "integration_enabled_field_present": "isEnabled" in integration,
        "integration_enabled": integration.get("isEnabled") is True,
        "expected_alias_exact": len(exact) == 1,
        "expected_alias_normalized": len(normalized) == 1,
        "expected_alias_ambiguous": len(exact) > 1 or len(normalized) > 1,
        "expected_key_identifier_present": len(exact) == 1 and bool(exact[0].get("keyId")),
    }


def inspect(token, opener=None):
    result = {"status": "NOT_AUTHENTICATED", "app_id": APP_ID,
              "app_owner_verified": False, "personal_context_owns_app": False,
              "apple_authentication_verified": False, "integration_resolution_verified": False,
              "signing_ready": False, "resources_modified": False,
              "response_contents_saved": False, "builds_started": 0}
    if not isinstance(token, str) or not re.fullmatch(r"[!-~]{20,4096}", token.strip()):
        return {**result, "status": "CODEMAGIC_TOKEN_INVALID"}
    token = token.strip()
    opener = opener or urllib.request.build_opener(NoRedirect())

    def get(path, stage):
        # Every request is GET. Only the target app, its known failed build, the
        # authenticated owner context and that app's validated owner team are used.
        if path not in ("/apps/" + APP_ID, "/builds/" + BUILD_ID, "/user") and not (
                path.startswith("/team/") and valid_id(path.removeprefix("/team/"))):
            raise Unavailable("REQUEST_SCOPE")
        request = urllib.request.Request("https://api.codemagic.io" + path, method="GET",
            headers={"x-auth-token": token, "Accept": "application/json",
                     "User-Agent": "AtodeYaruBox-Integration-ReadOnly"})
        try:
            with opener.open(request, timeout=15) as response:
                raw = response.read(LIMIT + 1)
            if len(raw) > LIMIT:
                raise Unavailable(stage)
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                raise Unavailable(stage)
            return payload
        except urllib.error.HTTPError as error:
            raise Unavailable(stage, int(error.code)) from None
        except (RefusedRedirect, urllib.error.URLError, TimeoutError, OSError, ValueError, TypeError):
            raise Unavailable(stage) from None

    try:
        application = get("/apps/" + APP_ID, "APP").get("application", {})
        if not isinstance(application, dict) or application.get("_id") != APP_ID:
            raise Unavailable("APP_IDENTITY")
        owner = application.get("ownerTeam")
        if not valid_id(owner):
            payload = get("/builds/" + BUILD_ID, "KNOWN_BUILD")
            application, build = payload.get("application", {}), payload.get("build", {})
            if (not isinstance(application, dict) or application.get("_id") != APP_ID
                    or not isinstance(build, dict) or build.get("_id") != BUILD_ID):
                raise Unavailable("KNOWN_BUILD_IDENTITY")
            owner = application.get("ownerTeam")
        if not valid_id(owner):
            raise Unavailable("APP_OWNER")
        result["app_owner_verified"] = True
        user = get("/user", "PERSONAL_CONTEXT").get("user", {})
        if not isinstance(user, dict) or user.get("ok") is not True or not valid_id(user.get("activeTeam")):
            raise Unavailable("PERSONAL_CONTEXT_IDENTITY")
        personal = user["activeTeam"] == owner
        result["personal_context_owns_app"] = personal
        personal_meta = alias_metadata(user)
        result["personal_expected_alias_exact"] = personal_meta["expected_alias_exact"]
        if personal:
            context = user
        else:
            context = get("/team/" + owner, "APP_TEAM_CONTEXT").get("team", {})
            if not isinstance(context, dict) or context.get("_id") != owner:
                raise Unavailable("APP_TEAM_IDENTITY")
        result.update(alias_metadata(context))
        result["status"] = "APP_INTEGRATION_METADATA_READ"
        return result
    except Unavailable as error:
        result.update(status="CONTEXT_READ_UNAVAILABLE", failed_stage=error.stage)
        if error.code is not None:
            result["http_status"] = error.code
        return result
    except Exception:
        return {**result, "status": "CONTEXT_READ_UNAVAILABLE", "failed_stage": "UNEXPECTED_RESPONSE"}


def main():
    write_report(REPORT, {"status": "NOT_RUN", "app_id": APP_ID})
    token = os.environ.pop("CODEMAGIC_API_TOKEN", "")
    result = inspect(token)
    token = ""
    result["checked_at"] = datetime.now(timezone.utc).isoformat()
    source = os.environ.get("GITHUB_SHA", "")
    if re.fullmatch(r"[0-9a-f]{40}", source):
        result["source_commit"] = source
    write_report(REPORT, result)
    print(result["status"])
    return 0 if result["status"] == "APP_INTEGRATION_METADATA_READ" else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Read one known build and its non-secret Apple preflight report; no writes."""
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.parse
import urllib.request

from tools.codemagic_read_access import APP_ID, NoRedirect, RefusedRedirect, write_report

BUILD = "6ac9b97b2e8bb15cf3a74942"
COMMIT = "1a385cad809bfe4303dca3207143e2c6db71288a"
BRANCH = "codex/apple-alias-encrypted-a34e3d9"
API = "https://codemagic.io/api/v3/builds/" + BUILD
NAME = "apple-signing-preflight.json"
REPORT = Path("artifacts/codemagic-apple-evidence.json")
IDS = ("jp.atodeyarubox.app", "jp.atodeyarubox.app.share", "jp.atodeyarubox.app.widgets")
DIAGNOSTICS = {"INTEGRATION_CREDENTIALS_MISSING", "INTEGRATION_CREDENTIALS_INVALID", "JWT_DEPENDENCY_MISSING",
               "JWT_SIGNING_FAILED", "REDIRECT_REFUSED", "UNAPPROVED_ROUTE", "UNAPPROVED_IDENTIFIER",
               "UNAPPROVED_CERTIFICATE_QUERY", "RESPONSE_LIMIT_EXCEEDED", "APPLE_CONNECTION_FAILED",
               "APPLE_RESPONSE_INVALID", "PAGINATED_RESPONSE_REQUIRES_REVIEW", "BUNDLE_IDENTIFIER_AMBIGUOUS",
               "CERTIFICATE_RESPONSE_INVALID", "UNEXPECTED_PREFLIGHT_FAILURE", "PRIVATE_KEY_FORMAT_INVALID",
               "PRIVATE_KEY_REFERENCE_REFUSED", "PRIVATE_KEY_REFERENCE_UNAVAILABLE"}


def sanitize(payload):
    if not isinstance(payload, dict) or payload.get("status") not in ("NOT_VERIFIED", "APPLE_READ_AUTHENTICATED", "NOT_RUN"):
        return None
    for key in ("signed_build_ready", "apple_resources_modified", "binary_uploaded", "new_payment_enabled"):
        if payload.get(key) is not False:
            return None
    if type(payload.get("authentication_verified")) is not bool:
        return None
    result = {k: payload[k] for k in ("status", "authentication_verified", "signed_build_ready",
        "apple_resources_modified", "binary_uploaded", "new_payment_enabled")}
    for field, allowed in (("private_key_input_format", {"PEM", "ESCAPED_PEM", "BASE64_PEM", "FILE_REFERENCE"}),
                           ("signing_error_kind", {"VALUE_ERROR", "INVALID_KEY", "UNSUPPORTED_ALGORITHM", "IMPORT_ERROR", "NOT_IMPLEMENTED", "UNKNOWN"})):
        if field in payload:
            if not isinstance(payload[field], str) or payload[field] not in allowed:
                return None
            result[field] = payload[field]
    diagnostic = payload.get("diagnostic")
    if diagnostic is not None:
        if diagnostic not in DIAGNOSTICS and (not isinstance(diagnostic, str) or not re.fullmatch(r"APPLE_HTTP_[1-5][0-9]{2}", diagnostic)):
            return None
        result["diagnostic"] = diagnostic
    if payload["status"] == "APPLE_READ_AUTHENTICATED":
        ids = payload.get("bundle_identifiers")
        count = payload.get("distribution_certificates_returned")
        if (payload["authentication_verified"] is not True or not isinstance(ids, dict) or set(ids) != set(IDS)
                or any(v not in ("EXISTS", "NOT_REGISTERED") for v in ids.values())
                or type(count) is not int or not 0 <= count <= 200):
            return None
        result.update(bundle_identifiers=ids, distribution_certificates_returned=count)
    elif payload["authentication_verified"]:
        return None
    return result


def allowed_download(url):
    if not isinstance(url, str) or len(url) > 8192:
        return False
    try:
        parsed = urllib.parse.urlsplit(url)
        return (parsed.scheme == "https" and not parsed.username and not parsed.password
                and parsed.port in (None, 443) and parsed.hostname in ("codemagic.io", "api.codemagic.io", "storage.googleapis.com")
                and urllib.parse.unquote(parsed.path).endswith("/" + NAME) and not parsed.fragment)
    except ValueError:
        return False


def log_diagnostic(raw):
    text = raw.decode("utf-8", errors="replace")
    result = {}
    for flag, needle in (("pip_no_matching_distribution", "No matching distribution found"),
                         ("pip_certificate_error", "CERTIFICATE_VERIFY_FAILED"),
                         ("python_module_missing", "ModuleNotFoundError"),
                         ("unit_checks_failed", "FAILED (")):
        result[flag] = needle in text
    result["unit_checks_passed"] = bool(re.search(r"Ran 13 tests[^\n]*\n\s*\nOK(?:\n|$)", text))
    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", text):
        try:
            candidate, _ = decoder.raw_decode(text[match.start():])
        except ValueError:
            continue
        report = sanitize(candidate)
        if report:
            result["apple_report"] = report
            break
    return result


def read_known_log(token, opener, download_opener):
    req = urllib.request.Request("https://api.codemagic.io/builds/" + BUILD, method="GET",
        headers={"x-auth-token": token.strip(), "Accept": "application/json"})
    with opener.open(req, timeout=15) as response:
        raw = response.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024:
        return {"log_diagnostic": "METADATA_LIMIT"}
    payload = json.loads(raw)
    app, build = payload.get("application", {}), payload.get("build", {})
    if app.get("_id") != APP_ID or build.get("_id") != BUILD:
        return {"log_diagnostic": "LOG_BUILD_IDENTITY_UNVERIFIED"}
    actions = build.get("buildActions", [])
    if not isinstance(actions, list) or len(actions) < 3:
        return {"log_diagnostic": "LOG_ACTION_UNAVAILABLE"}
    step = actions[2]
    expected = "Verify Apple API authentication without changing apps or certificates"
    if not isinstance(step, dict) or expected not in (step.get("name"), step.get("title")):
        return {"log_diagnostic": "LOG_ACTION_IDENTITY_UNVERIFIED"}
    subactions = step.get("subactions")
    child = subactions[0] if isinstance(subactions, list) and subactions and isinstance(subactions[0], dict) else {}
    inline = step.get("logs") or child.get("logs")
    if isinstance(inline, str) and len(inline.encode("utf-8")) <= 256 * 1024:
        return {"log_diagnostic": "KNOWN_STEP_LOG_CLASSIFIED", **log_diagnostic(inline.encode("utf-8"))}
    url = step.get("logUrl") or child.get("logUrl")
    if not isinstance(url, str) or len(url) > 8192:
        endpoint = "https://api.codemagic.io/builds/" + BUILD + "/logs/2"
        request = urllib.request.Request(endpoint, method="GET", headers={"x-auth-token": token.strip()})
        with opener.open(request, timeout=15) as response:
            raw = response.read(256 * 1024 + 1)
        if len(raw) > 256 * 1024:
            return {"log_diagnostic": "LOG_LIMIT"}
        return {"log_diagnostic": "STEP_LOG_ENDPOINT_CLASSIFIED", **log_diagnostic(raw)}
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != "https" or parsed.username or parsed.password or parsed.port not in (None, 443)
            or parsed.hostname not in ("storage.googleapis.com", "api.codemagic.io", "codemagic.io")
            or parsed.fragment):
        return {"log_diagnostic": "LOG_URL_REFUSED"}
    # The token may reach only Codemagic's own log endpoint. It never reaches
    # storage hosts or redirects, and raw logs/download URLs are never reported.
    headers = {}
    if parsed.hostname == "api.codemagic.io":
        # This one URL comes only from step 2 of the verified build, after the
        # exact app/branch/commit gate. Codemagic's log URLs are opaque routes.
        # The same-origin token cannot follow redirects or reach other hosts.
        headers["x-auth-token"] = token.strip()
    reader = opener if headers else download_opener
    with reader.open(urllib.request.Request(url, method="GET", headers=headers), timeout=15) as response:
        raw = response.read(256 * 1024 + 1)
    if len(raw) > 256 * 1024:
        return {"log_diagnostic": "LOG_LIMIT"}
    return {"log_diagnostic": "KNOWN_STEP_LOG_CLASSIFIED", **log_diagnostic(raw)}


def inspect(token, opener=None, download_opener=None):
    result = {"status": "NOT_VERIFIED", "app_id": APP_ID, "build_id": BUILD, "build_commit": COMMIT,
              "private_key_used": False, "resources_modified": False, "builds_started": 0}
    if not isinstance(token, str) or not re.fullmatch(r"[!-~]{20,4096}", token.strip()):
        return {**result, "diagnostic": "TOKEN_INVALID"}
    opener = opener or urllib.request.build_opener(NoRedirect())
    download_opener = download_opener or urllib.request.build_opener(NoRedirect())
    try:
        request = urllib.request.Request(API, method="GET", headers={"x-auth-token": token.strip(), "Accept": "application/json"})
        with opener.open(request, timeout=15) as response:
            raw = response.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            return {**result, "diagnostic": "BUILD_RESPONSE_LIMIT"}
        build = json.loads(raw).get("data")
        if (not isinstance(build, dict) or build.get("id") != BUILD or build.get("app_id") != APP_ID
                or build.get("branch") != BRANCH or (build.get("commit") or {}).get("hash") != COMMIT):
            return {**result, "diagnostic": "BUILD_IDENTITY_UNVERIFIED"}
        state = build.get("status")
        if state not in ("finished", "failed", "canceled", "timeout", "skipped"):
            return {**result, "diagnostic": "BUILD_NOT_FINISHED"}
        result["build_status"] = state
        artifacts = build.get("artifacts")
        if not isinstance(artifacts, list) or len(artifacts) > 50:
            return {**result, "diagnostic": "ARTIFACT_LIST_UNVERIFIED"}
        matching = [a for a in artifacts if isinstance(a, dict) and a.get("name") == NAME]
        result["report_artifact_count"] = len(matching)
        if not matching:
            return {**result, "status": "KNOWN_STEP_DIAGNOSTICS_READ", **read_known_log(token, opener, download_opener)}
        if len(matching) != 1 or not allowed_download(matching[0].get("short_lived_download_url")):
            return {**result, "diagnostic": "REPORT_ARTIFACT_UNAVAILABLE"}
        # Never forward the Codemagic token to artifact storage, redirects or logs.
        download = urllib.request.Request(matching[0]["short_lived_download_url"], method="GET", headers={"Accept": "application/json"})
        with download_opener.open(download, timeout=15) as response:
            raw = response.read(64 * 1024 + 1)
        if len(raw) > 64 * 1024:
            return {**result, "diagnostic": "REPORT_RESPONSE_LIMIT"}
        report = sanitize(json.loads(raw))
        if report is None:
            return {**result, "diagnostic": "REPORT_UNVERIFIED"}
        return {**result, "status": "KNOWN_APPLE_REPORT_READ", "apple_report": report}
    except urllib.error.HTTPError as error:
        return {**result, "diagnostic": "HTTP_" + str(int(error.code))}
    except (RefusedRedirect, urllib.error.URLError, TimeoutError, OSError, ValueError, TypeError, AttributeError):
        return {**result, "diagnostic": "REQUEST_UNAVAILABLE"}
    except Exception:
        return {**result, "diagnostic": "UNEXPECTED_RESPONSE"}


def main():
    write_report(REPORT, {"status": "NOT_RUN", "app_id": APP_ID})
    token = os.environ.pop("CODEMAGIC_API_TOKEN", "")
    result = inspect(token)
    token = ""
    source = os.environ.get("GITHUB_SHA", "")
    if re.fullmatch(r"[0-9a-f]{40}", source):
        result["source_commit"] = source
    write_report(REPORT, result)
    print(result["status"])
    return 0 if result["status"] in ("KNOWN_APPLE_REPORT_READ", "KNOWN_STEP_DIAGNOSTICS_READ") else 1


if __name__ == "__main__":
    raise SystemExit(main())

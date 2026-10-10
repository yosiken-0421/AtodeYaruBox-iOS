"""Create only an app-local encrypted variable containing a known public alias."""
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.request

from tools.codemagic_integration_read import inspect, valid_id
from tools.codemagic_read_access import APP_ID, NoRedirect, RefusedRedirect, write_report

GROUP = "atodeyarubox-apple-alias-d43f7c2"
NAME = "ASC_KEY_ALIAS"
VALUE = "    AtodeYaruBox-CI"
BASE = "https://codemagic.io/api/v3"
APP_PATH = "/apps/" + APP_ID + "/variable-groups"
REPORT = Path("artifacts/codemagic-alias-variable.json")
LIMIT = 256 * 1024


class Halt(Exception):
    pass


def single_page(payload):
    entries = payload.get("data")
    pages = payload.get("total_pages", 1)
    current = payload.get("current_page", 1)
    return (isinstance(entries, list) and type(pages) is int and type(current) is int
            and current == 1 and (pages == 1 or pages == 0 and entries == []))


def configure(token, opener=None, gate=None, checkpoint=None):
    result = {"status": "NOT_CONFIGURED", "app_id": APP_ID, "group_name": GROUP,
              "variable_name": NAME, "private_key_used": False, "apple_resources_modified": False,
              "billing_modified": False, "builds_started": 0, "app_group_created": False,
              "encrypted_alias_variable_created": False}
    opener = opener or urllib.request.build_opener(NoRedirect())
    gate = gate if gate is not None else inspect(token, opener)
    if (gate.get("status") != "APP_INTEGRATION_METADATA_READ" or gate.get("app_owner_verified") is not True
            or gate.get("personal_context_owns_app") is not True or gate.get("free_allowance_verified") is not True
            or gate.get("paid_cicd_subscription_present") is not False or gate.get("free_m2_remaining_seconds", 0) < 1200
            or gate.get("normalized_alias_codepoints") != list(map(ord, VALUE))):
        return {**result, "status": "CURRENT_APP_OWNER_ALIAS_AND_FREE_ALLOWANCE_REQUIRED"}
    if not isinstance(token, str) or not re.fullmatch(r"[!-~]{20,4096}", token.strip()):
        return {**result, "status": "TOKEN_INVALID"}
    result.update(free_allowance_verified=True, paid_cicd_subscription_present=False,
                  free_m2_remaining_seconds=gate["free_m2_remaining_seconds"])
    token = token.strip()
    group_id = None

    def request(path, method="GET", body=None):
        allowed = path == APP_PATH and (method == "GET" or method == "POST" and body == {"name": GROUP})
        if valid_id(group_id) and path == "/variable-groups/" + group_id + "/variables":
            allowed = method == "GET" or method == "POST" and body == {"secure": True, "variables": [{"name": NAME, "value": VALUE}]}
        if not allowed:
            raise Halt("REQUEST_SCOPE_REFUSED")
        if method == "POST":
            result["status"] = "MUTATION_RESERVED_OUTCOME_UNKNOWN"
            if checkpoint:
                checkpoint(dict(result))
        req = urllib.request.Request(BASE + path, method=method,
            data=None if body is None else json.dumps(body).encode(), headers={
                "x-auth-token": token, "Content-Type": "application/json", "Accept": "application/json",
                "User-Agent": "AtodeYaruBox-AppLocal-Alias"})
        try:
            with opener.open(req, timeout=15) as response:
                raw = response.read(LIMIT + 1)
            if len(raw) > LIMIT:
                raise Halt("RESPONSE_LIMIT_EXCEEDED")
            value = json.loads(raw) if raw else {}
            if not isinstance(value, dict):
                raise Halt("RESPONSE_UNVERIFIED")
            return value
        except urllib.error.HTTPError as error:
            raise Halt("HTTP_" + str(int(error.code))) from None
        except (RefusedRedirect, urllib.error.URLError, TimeoutError, OSError, ValueError):
            raise Halt("REQUEST_OUTCOME_UNAVAILABLE") from None

    try:
        groups = request(APP_PATH)
        entries = groups.get("data")
        if not single_page(groups):
            result["group_list_is_array"] = isinstance(entries, list)
            for field in ("total_pages", "current_page"):
                if type(groups.get(field)) is int and 0 <= groups[field] <= 100000:
                    result["group_list_" + field] = groups[field]
            raise Halt("APP_GROUP_LIST_UNVERIFIED")
        if any(not isinstance(entry, dict) or entry.get("name") == GROUP for entry in entries):
            raise Halt("EXISTING_GROUP_NOT_MODIFIED")
        created = request(APP_PATH, "POST", {"name": GROUP}).get("data", {})
        if not isinstance(created, dict) or created.get("name") != GROUP or not valid_id(created.get("id")):
            raise Halt("GROUP_CREATION_OUTCOME_UNVERIFIED")
        group_id = created["id"]
        result["app_group_created"] = True
        variables_path = "/variable-groups/" + group_id + "/variables"
        variables = request(variables_path)
        if variables.get("data") != [] or not single_page(variables):
            raise Halt("NEW_GROUP_NOT_EMPTY")
        request(variables_path, "POST", {"secure": True, "variables": [{"name": NAME, "value": VALUE}]})
        verified = request(variables_path).get("data")
        if (not isinstance(verified, list) or len(verified) != 1 or not isinstance(verified[0], dict)
                or verified[0].get("name") != NAME or verified[0].get("secure") is not True):
            raise Halt("ENCRYPTED_VARIABLE_METADATA_UNVERIFIED")
        result.update(status="APP_LOCAL_ENCRYPTED_ALIAS_CONFIGURED", encrypted_alias_variable_created=True)
        return result
    except Halt as error:
        return {**result, "status": "CONFIGURATION_UNAVAILABLE", "diagnostic": str(error)}
    except Exception:
        return {**result, "status": "CONFIGURATION_UNAVAILABLE", "diagnostic": "UNEXPECTED_RESPONSE"}


def main():
    write_report(REPORT, {"status": "NOT_RUN", "app_id": APP_ID})
    token = os.environ.pop("CODEMAGIC_API_TOKEN", "")
    result = configure(token, checkpoint=lambda record: write_report(REPORT, record))
    token = ""
    source = os.environ.get("GITHUB_SHA", "")
    if re.fullmatch(r"[0-9a-f]{40}", source):
        result["source_commit"] = source
    write_report(REPORT, result)
    print(result["status"])
    return 0 if result["status"] == "APP_LOCAL_ENCRYPTED_ALIAS_CONFIGURED" else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Extract safe HCX transport metrics from structured application logs."""
from __future__ import annotations

import argparse
import ast
import json
import re
from collections import Counter
from pathlib import Path

FIELD = re.compile(r"(request_id|case_id|attempt|started_at|duration_ms|success|exception_class|transport_error_type|upstream_http_status|retry_after|timeout|retry|final_exhausted|status)=('[^']*'|[^ ]+)")


def value(raw: str):
    if raw in {"None", "True", "False"}:
        return {"None": None, "True": True, "False": False}[raw]
    if raw.startswith("'"):
        return ast.literal_eval(raw)
    try:
        return float(raw) if "." in raw else int(raw)
    except ValueError:
        return raw


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--evaluation")
    args = parser.parse_args()
    attempts = []
    for line in Path(args.log).read_text(encoding="utf-8").splitlines():
        if "hcx_transport_attempt" not in line:
            continue
        attempts.append({key: value(raw) for key, raw in FIELD.findall(line)})
    statuses = Counter(str(x["upstream_http_status"]) for x in attempts if x.get("upstream_http_status") is not None)
    cases = {x.get("case_id") for x in attempts if x.get("case_id")}
    successful_cases = {x.get("case_id") for x in attempts if x.get("case_id") and x.get("success")}
    result = {
        "summary": {
            "attempts": len(attempts),
            "case_invocations": len(cases),
            "case_transport_success": len(successful_cases),
            "retry_attempts": sum(bool(x.get("retry")) for x in attempts),
            "upstream_status_distribution": dict(statuses),
            "upstream_429": statuses["429"],
            "upstream_5xx": sum(n for status, n in statuses.items() if status.startswith("5")),
            "read_timeout": sum(x.get("exception_class") == "ReadTimeout" for x in attempts),
            "other_transport_errors": sum(not x.get("success") and not x.get("timeout") and x.get("upstream_http_status") is None for x in attempts),
            "retry_exhausted": sum(bool(x.get("final_exhausted")) for x in attempts),
            "retry_after_present": sum(x.get("retry_after") is not None for x in attempts),
        },
        "attempts": attempts,
    }
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.evaluation:
        evaluation_path = Path(args.evaluation)
        evaluation = json.loads(evaluation_path.read_text(encoding="utf-8"))
        evaluation["summary"]["server_transport"] = result["summary"]
        evaluation_path.write_text(json.dumps(evaluation, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()

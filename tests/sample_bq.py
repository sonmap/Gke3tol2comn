#!/usr/bin/env python3
"""RSVP GKE Autopilot pre-cutover read-only BigQuery smoke test.

- Uses existing mounted service-account JSON key; never prints key contents.
- Exit 0: job succeeded. Exit 1: auth/query failure.
- Does not mutate any production BigQuery objects.
"""
import os
import sys
from pathlib import Path

from google.cloud import bigquery
from google.oauth2 import service_account

PROJECT_ID = os.environ.get("BQ_PROJECT", "gcp-prod-edp-lake")
TABLE_ID = os.environ.get(
    "BQ_TEST_TABLE", "gcp-prod-edp-lake.DLKUDF.L2MQ_TL_SUBJ_H_TEST"
)
KEY_PATH = os.environ.get("BQ_KEY_PATH", "/home/jupyter/.oefj")


def main() -> int:
    client = None
    try:
        path = Path(KEY_PATH)
        if not path.is_file():
            raise FileNotFoundError(f"Service account key file not found: {path}")

        credentials = service_account.Credentials.from_service_account_file(
            str(path),
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        print(f"[INFO] key_path={KEY_PATH}", flush=True)
        print(f"[INFO] service_account={credentials.service_account_email}", flush=True)
        print(f"[INFO] job_project={PROJECT_ID}", flush=True)
        print(f"[INFO] table={TABLE_ID}", flush=True)

        client = bigquery.Client(project=PROJECT_ID, credentials=credentials)
        # The table identifier is controlled by the operator, not by untrusted user input.
        if len(TABLE_ID.split(".")) != 3:
            raise ValueError("BQ_TEST_TABLE must be project.dataset.table")
        query = f"SELECT 1 AS connected FROM \u0060{TABLE_ID}\u0060 LIMIT 1"
        config = bigquery.QueryJobConfig(
            use_query_cache=False,
            maximum_bytes_billed=100 * 1024 * 1024,  # 100 MiB ceiling
        )
        job = client.query(query, job_config=config)
        rows = list(job.result(timeout=120))
        print(f"[SUCCESS] BQ SELECT job_id={job.job_id} rows={len(rows)}")
        print(f"[INFO] bytes_processed={job.total_bytes_processed}")
        print(f"[INFO] bytes_billed={job.total_bytes_billed}")
        return 0
    except Exception as exc:
        print(f"[ERROR] BigQuery smoke test failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    finally:
        if client is not None:
            client.close()


if __name__ == "__main__":
    sys.exit(main())

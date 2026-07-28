import delta_sharing
import pyarrow
import pandas as pd
import requests
import argparse

import sys
import json
import os
import ssl
from pathlib import Path


def load_profile(path="profile.share"):
    with open(path, "r") as f:
        return json.load(f)


def profile_headers(profile):
    token = profile.get("bearerToken", "")
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def api_url(profile, path):
    return profile["endpoint"].rstrip("/") + path


def request_verify(args):
    insecure = args.insecure_tls or os.getenv("OPENSHARING_INSECURE_TLS", "false").lower() in {"1", "true", "yes"}
    if insecure:
        return False

    explicit_bundle = args.ca_bundle or os.getenv("OPENSHARING_CA_BUNDLE") or os.getenv("REQUESTS_CA_BUNDLE")
    if explicit_bundle:
        return explicit_bundle

    default_paths = ssl.get_default_verify_paths()
    if default_paths.cafile and Path(default_paths.cafile).exists():
        return default_paths.cafile

    repo_bundle = Path(__file__).resolve().parent / "certs" / "storagegrid-ca.crt"
    if repo_bundle.exists():
        return str(repo_bundle)

    return True

def test_query(profile_path):
    # To run this, you need to first use your browser to log into Dex, 
    # extract the ID Token, and insert it in profile.share
    
    data = load_profile(profile_path)
        
    if "INSERT_TOKEN_HERE" in data.get("bearerToken", ""):
        print("ERROR: Please update 'profile.share' with your real Bearer Token first!")
        sys.exit(1)

    print("Connecting to OpenSharing Server for NetApp StorageGRID and Versity S3 Gateway...")
    try:
        # Load the sharing profile
        client = delta_sharing.SharingClient(profile_path)

        preferred_share = os.getenv("SHARE")
        preferred_schema = os.getenv("SCHEMA")
        preferred_table = os.getenv("TABLE", "iot_silver_table")

        tables = client.list_all_tables()
        if not tables:
            print("ERROR: No tables returned by OpenSharing control plane.")
            sys.exit(1)

        available = [f"{t.share}.{t.schema}.{t.name}" for t in tables]
        share_names = sorted({t.share for t in tables})
        print(f"Available shares: {share_names}")
        print(f"Available tables: {available}")

        matching = [
            t for t in tables
            if (preferred_share is None or t.share == preferred_share)
            and (preferred_schema is None or t.schema == preferred_schema)
        ]

        if not matching:
            print("ERROR: No tables match requested SHARE/SCHEMA filters.")
            sys.exit(1)

        selected = next((t for t in matching if t.name == preferred_table), matching[0])
        share_name = selected.share
        schema_name = selected.schema
        table_name = selected.name

        print(f"Requesting table '{share_name}.{schema_name}.{table_name}'...")

        # Databricks delta-sharing syntax uses the profile path + discovered table details
        table_path = f"{profile_path}#{share_name}.{schema_name}.{table_name}"
        
        print("Loading Parquet data from S3...")
        pdf = delta_sharing.load_as_pandas(table_path)
        
        print("\nSUCCESS! Successfully loaded external Parquet data:")
        print(pdf.head())
        print(f"\nTotal rows imported via S3: {len(pdf)}")
        
    except Exception as e:
        print(f"\nFailed: {e}")

def test_query_tables_simple(profile_path):
    """Lighter test querying the simple unpartitioned test-object.parquet file."""
    print("\n--- Running Simple Test Query on Tables ---")
    try:
        table_path = f"{profile_path}#report-share.report-schema.report_table"
        print(f"Requesting table 'report-share.report-schema.report_table'...")
        pdf = delta_sharing.load_as_pandas(table_path)
        print("\nSUCCESS! Successfully loaded simple Parquet test data:")
        print(pdf.head())
        print(f"\nTotal rows imported via S3: {len(pdf)}")
    except Exception as e:
        print(f"\nSimple test query failed (safe to ignore if simple mock table is not configured): {e}")

def test_query_volumes_simple(profile_path, verify):
    print("\n--- Running Simple Test Query on Volumes ---")
    try:
        profile = load_profile(profile_path)
        headers = profile_headers(profile)
        share_name = os.getenv("VOLUME_SHARE", "files-share")
        schema_name = os.getenv("VOLUME_SCHEMA", "log-schema")
        volume_name = os.getenv("VOLUME", "docs-dir")

        print(f"Requesting volume '{share_name}.{schema_name}.{volume_name}'...")

        list_url = api_url(profile, f"/shares/{share_name}/schemas/{schema_name}/volumes/{volume_name}/files")
        list_response = requests.get(list_url, headers=headers, timeout=30, verify=verify)
        list_response.raise_for_status()
        payload = list_response.json()
        items = payload.get("items", [])
        if not items:
            print("No files returned for the volume.")
            return

        requested_file = os.getenv("VOLUME_FILE")
        selected = next((item for item in items if item.get("file_path") == requested_file), items[0])
        file_path = selected.get("file_path")
        print(f"Selected file: {file_path} ({selected.get('size', 'unknown')} bytes)")

        download_url = api_url(profile, f"/shares/{share_name}/schemas/{schema_name}/volumes/{volume_name}/files/download")
        download_response = requests.post(
            download_url,
            headers={**headers, "Content-Type": "application/json"},
            json={"file_path": file_path},
            timeout=30,
            verify=verify,
        )
        download_response.raise_for_status()
        presigned_url = download_response.json()["download_url"]
        print(f"Presigned URL obtained for volume file download: {presigned_url}")

        file_response = requests.get(presigned_url, timeout=30, verify=verify)
        file_response.raise_for_status()

        print("\nSUCCESS! First 5 lines:")
        for line in file_response.text.splitlines()[:5]:
            print(line)

    except Exception as e:
        print(f"\nSimple test query failed (safe to ignore if simple mock volume is not configured): {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OpenSharing table/volume smoke client")
    parser.add_argument("--profile", default="profile.share", help="Path to Delta Sharing profile")
    parser.add_argument("--insecure-tls", action="store_true", help="Disable TLS certificate verification for HTTP calls")
    parser.add_argument("--ca-bundle", default="", help="Path to CA bundle PEM for HTTPS verification")
    args = parser.parse_args()

    profile_path = str(Path(args.profile).resolve())
    verify = request_verify(args)

    if verify is False:
        requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)

    test_query(profile_path)
    test_query_tables_simple(profile_path)
    test_query_volumes_simple(profile_path, verify)


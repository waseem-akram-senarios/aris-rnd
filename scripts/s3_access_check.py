import os
import sys
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from dotenv import load_dotenv


def _ensure_aws_creds_from_opensearch_env() -> None:
    """Fallback: reuse AWS OpenSearch creds if standard AWS creds are not set."""
    if not os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_OPENSEARCH_ACCESS_KEY_ID"):
        os.environ["AWS_ACCESS_KEY_ID"] = os.getenv("AWS_OPENSEARCH_ACCESS_KEY_ID")
    if not os.getenv("AWS_SECRET_ACCESS_KEY") and os.getenv("AWS_OPENSEARCH_SECRET_ACCESS_KEY"):
        os.environ["AWS_SECRET_ACCESS_KEY"] = os.getenv("AWS_OPENSEARCH_SECRET_ACCESS_KEY")


def main() -> int:
    load_dotenv(dotenv_path=os.getenv("DOTENV_PATH") or ".env")

    bucket = os.getenv("S3_BUCKET", "intelycx-waseem-s3-bucket")
    region = (
        os.getenv("AWS_DEFAULT_REGION")
        or os.getenv("AWS_REGION")
        or os.getenv("AWS_OPENSEARCH_REGION")
        or "us-east-2"
    )

    _ensure_aws_creds_from_opensearch_env()

    print("=== S3 Access Check ===")
    print("Bucket:", bucket)
    print("Region:", region)
    print("Has AWS_ACCESS_KEY_ID:", bool(os.getenv("AWS_ACCESS_KEY_ID")))
    print("Has AWS_SECRET_ACCESS_KEY:", bool(os.getenv("AWS_SECRET_ACCESS_KEY")))
    print("Has AWS_SESSION_TOKEN:", bool(os.getenv("AWS_SESSION_TOKEN")))

    try:
        sts = boto3.client("sts", region_name=region)
        ident = sts.get_caller_identity()
        print("CallerIdentity:", {k: ident.get(k) for k in ["Account", "Arn", "UserId"]})
    except NoCredentialsError as e:
        print("❌ NoCredentialsError:", str(e))
        return 2
    except Exception as e:
        print("❌ STS error:", type(e).__name__, str(e))
        return 3

    s3 = boto3.client("s3", region_name=region)

    print("\n[1] List bucket (ListObjectsV2)")
    try:
        resp = s3.list_objects_v2(Bucket=bucket, MaxKeys=5)
        keys = [c["Key"] for c in resp.get("Contents", [])]
        print("✅ list_objects_v2 OK. Sample keys:", keys)
    except ClientError as e:
        print("❌ list_objects_v2 FAILED:", e.response.get("Error", {}))
        return 10

    print("\n[2] Put/Get/Delete test object")
    key = os.getenv("S3_TEST_KEY", "aris-access-check/test_object.txt")
    body = b"hello from s3 access check"

    try:
        s3.put_object(Bucket=bucket, Key=key, Body=body)
        print("✅ put_object OK:", key)

        got = s3.get_object(Bucket=bucket, Key=key)
        data = got["Body"].read()
        print("✅ get_object OK. Matches:", data == body)

        s3.delete_object(Bucket=bucket, Key=key)
        print("✅ delete_object OK")
    except ClientError as e:
        print("❌ object operation FAILED:", e.response.get("Error", {}))
        return 11

    print("\n✅ SUCCESS: You have List + Get/Put/Delete access to this bucket.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

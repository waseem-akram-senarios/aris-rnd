import logging
import os
import sys
from datetime import datetime

import boto3
from botocore.exceptions import ClientError
from botocore.exceptions import NoCredentialsError

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class ObjectWrapper:
    """Encapsulates S3 object actions."""

    def __init__(self, s3_object):
        """Initialize the wrapper.

        :param s3_object: A Boto3 Object resource.
        """
        self.object = s3_object
        self.key = self.object.key

    def put(self, data):
        """Upload data to the object.

        :param data: Bytes or a filename (string) to open in rb.
        """
        put_data = data
        if isinstance(data, str):
            try:
                put_data = open(data, "rb")
            except IOError:
                logger.exception("Expected file name or binary data, got '%s'.", data)
                raise

        try:
            self.object.put(Body=put_data)
            self.object.wait_until_exists()
            logger.info(
                "Put object '%s' to bucket '%s'.",
                self.object.key,
                self.object.bucket_name,
            )
        except ClientError:
            logger.exception(
                "Couldn't put object '%s' to bucket '%s'.",
                self.object.key,
                self.object.bucket_name,
            )
            raise
        finally:
            if getattr(put_data, "close", None):
                put_data.close()


def main():
    profile = None
    if len(sys.argv) > 1:
        profile = sys.argv[1]
    if profile is None:
        profile = os.environ.get("AWS_PROFILE")

    try:
        session = boto3.Session(profile_name=profile) if profile else boto3.Session()
        sts = session.client("sts")
        ident = sts.get_caller_identity()
        print("CALLER_ARN:", ident.get("Arn"))
        print("CALLER_ACCOUNT:", ident.get("Account"))
    except NoCredentialsError:
        print("ERROR: boto3 could not locate AWS credentials.")
        print("Fix options:")
        print("  1) Export AWS credentials env vars (AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY[/AWS_SESSION_TOKEN]")
        print("  2) Configure a default profile in ~/.aws/credentials")
        print("  3) If you use SSO: run 'aws sso login --profile <name>' then run this script as: python3 test_object_wrapper.py <name>")
        print("  4) Or set: export AWS_PROFILE=<name> and rerun")
        raise

    bucket = "intelycx-waseem-s3-bucket"
    key = f"docs-test/wrapper-put-test-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.txt"

    s3 = session.resource("s3")
    obj = s3.Object(bucket, key)

    wrapper = ObjectWrapper(obj)
    wrapper.put(b"hello from ObjectWrapper.put()\n")

    # Hard verification via HEAD
    s3c = session.client("s3")
    head = s3c.head_object(Bucket=bucket, Key=key)

    print("SUCCESS")
    print("S3_URI:", f"s3://{bucket}/{key}")
    print("ETAG:", head.get("ETag"))


if __name__ == "__main__":
    main()

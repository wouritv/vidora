import os
from dotenv import load_dotenv
load_dotenv()
import logging

try:
    import boto3
    from botocore.config import Config
    from botocore.exceptions import ClientError
except ImportError:  # pragma: no cover - optional dependency in minimal test env
    boto3 = None

    class ClientError(Exception):
        pass

    Config = None

# Configure silent logging for boto3 and botocore
logging.getLogger('boto3').setLevel(logging.CRITICAL)
logging.getLogger('botocore').setLevel(logging.CRITICAL)
logging.getLogger('s3transfer').setLevel(logging.CRITICAL)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def upload_file_to_s3(file_path, bucket_name, s3_key):
    """
    Upload a file to an S3 bucket silently.
    """
    if not file_path or not bucket_name or not s3_key:
        return False

    s3_client = get_s3_client()
    if not s3_client:
        return False

    try:
        # Extra arguments for public read if needed, but the user didn't specify.
        # Given the bucket name, it might be for a web app.
        s3_client.upload_file(file_path, bucket_name, s3_key)
        return True
    except ClientError:
        return False
    except Exception:
        return False

import json
import time as time_module

# Simple in-memory cache for gallery clips
_clips_cache = {
    "data": None,
    "timestamp": 0
}
CACHE_TTL_SECONDS = 300  # 5 minutes

def get_s3_client():
    """Returns an authenticated S3 client."""
    access_key = os.environ.get('AWS_ACCESS_KEY_ID')
    secret_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
    region = os.environ.get('AWS_REGION', 'eu-west-3')

    if boto3 is None or not access_key or not secret_key:
        return None

    client_kwargs = {
        'service_name': 's3',
        'aws_access_key_id': access_key,
        'aws_secret_access_key': secret_key,
        'region_name': region,
    }
    if Config is not None:
        client_kwargs['config'] = Config(signature_version='s3v4')
    return boto3.client(**client_kwargs)

def generate_presigned_url(bucket_name, object_key, expiration=3600):
    """Generate a presigned URL to share an S3 object."""
    s3_client = get_s3_client()
    if not s3_client:
        return None
    try:
        response = s3_client.generate_presigned_url('get_object',
                                                    Params={'Bucket': bucket_name,
                                                            'Key': object_key},
                                                    ExpiresIn=expiration)
        return response
    except ClientError:
        logger.exception("Failed to generate presigned URL")
        return None


def delete_s3_object(bucket_name, object_key):
    """Delete one object from S3 bucket."""
    s3_client = get_s3_client()
    if not s3_client or not bucket_name or not object_key:
        return False
    try:
        s3_client.delete_object(Bucket=bucket_name, Key=object_key)
        return True
    except ClientError:
        return False
    except Exception:
        return False


def get_s3_object_size(bucket_name, object_key):
    """Return object size in bytes, or 0 if unknown."""
    s3_client = get_s3_client()
    if not s3_client or not bucket_name or not object_key:
        return 0
    try:
        response = s3_client.head_object(Bucket=bucket_name, Key=object_key)
        return int(response.get("ContentLength") or 0)
    except Exception:
        return 0


def upload_job_artifacts(directory, job_id):
    """
    Upload all generated clips and metadata for a job to S3.
    """
    bucket_name = os.environ.get('AWS_S3_BUCKET', 'my-clips-bucket')
    
    if not os.path.exists(directory):
        return

    for filename in os.listdir(directory):
        # Upload .mp4 clips and the metadata JSON
        if filename.endswith((".mp4", ".json")) and not filename.startswith("temp_"):
            file_path = os.path.join(directory, filename)
            s3_key = f"{job_id}/{filename}"
            upload_file_to_s3(file_path, bucket_name, s3_key)



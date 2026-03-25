
from dotenv import load_dotenv
load_dotenv(override=True)
import os
import boto3
from botocore.client import Config

client = boto3.client(
    's3',
    endpoint_url="https://s3.us-east-005.backblazeb2.com",
    aws_access_key_id=os.getenv("B2_KEY_ID"),
    aws_secret_access_key=os.getenv("B2_APP_KEY"),
    config=Config(signature_version='s3v4')
)
print("KEY:", os.getenv("B2_KEY_ID"))
try:
    response = client.list_buckets()
    print("SUCCESS")
except Exception as e:
    print("ERROR:", e)

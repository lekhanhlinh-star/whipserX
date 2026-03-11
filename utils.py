import boto3
import os

def upload_file_to_s3(file_path: str, bucket_name: str, s3_key: str):
    """
    Uploads a file to an S3 bucket 
    Args:
        file_path (str): Local path to the file to upload.
        bucket_name (str): Name of the S3 bucket.
        s3_key (str): The S3 object key (path in the bucket).

    Returns:
        url (str): The URL of the uploaded file.
    """
    s3_client = boto3.client('s3')
    try:
        s3_client.upload_file(file_path, bucket_name, s3_key)
        url = f"https://{bucket_name}.s3.amazonaws.com/{s3_key}"
        return url
    except Exception as e:
        print(f"Error uploading file to S3: {e}")
        return None

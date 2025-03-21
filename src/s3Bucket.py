import logging
from config import Config
from botocore.config import Config as botocore_config
import boto3
from botocore.exceptions import ClientError
from datetime import datetime, timezone
import os

logger = logging.getLogger(__name__)

# ********************************************* Clients *********************************************
def initialize_s3client(logger = logger):
    s3_client = boto3.client(
    's3',
    aws_access_key_id=Config.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=Config.AWS_SECRET_ACESS_KEY,
    region_name= 'eu-north-1',
    config=botocore_config(signature_version='s3v4')
    )
    logger.info("S3 client initialized")
    return s3_client

# ********************************************* Look for files *********************************************
def list_files_in_s3(logger = logger):
    """ List all files in S3 bucket """
    try:
        s3_client = initialize_s3client(logger)
        response = s3_client.list_objects_v2(
            Bucket=Config.BUCKET_NAME
        )
        if 'Contents' in response:
            logger.info(f"Files in S3 bucket: {response['Contents']}")
            return response['Contents']
        else:
            logger.info("No files found in S3 bucket.")
            return []
    except Exception as e:
        logger.error(f"Error listing files in S3: {e}")
        return None

def get_all_fileNames_in_s3(logger = logger):
    """ List all file names in S3 bucket """
    try:
        files = list_files_in_s3(logger)
        if files is None:
            return None
        file_names = [file['Key'] for file in files]
        logger.info(f"File names in S3 bucket: {file_names}")
        return file_names
    except Exception as e:
        logger.error(f"Error getting file names from S3: {e}")
        return None

def check_file_exists(file_name, file_size=None, s3_client = initialize_s3client(), logger = logger):
    """Check if a file already exist by checking the file name and size in the S3 bucker.

    Args:
        s3_client (boto3 client): client to interact with S3
        file_name (str) : name of the file to check
        file_size (int) : size of the file to check
        
    Returns:
        file name exists ? true : false
        file size matches ? true : false
    """
    try:
        logger.info(f"Checking if file exists in S3: {file_name}")
        response = s3_client.head_object(Bucket=Config.BUCKET_NAME, Key=file_name)
        
        # Check file size if provided
        if file_size is not None and response['ContentLength'] is not None:
            if response['ContentLength'] == file_size:
                logger.info(f"File exists in S3: {file_name}")
                return True, True
            else:
                logger.info(f"File name exists in S3 but with different size: {file_name}")
                return True, False
        else:
            logger.info(f"File does not exists in S3: {file_name}")
            return False, False
    except ClientError as e:
        if e.response['Error']['Code'] == '404':
            logger.info(f"File not found in S3: {file_name}")
            return False, False
        else:
            raise e

# ********************************************* open / download files *********************************************

def open_from_s3(file_name, logger = logger):
    """ Open file from S3 """
    try:
        s3_client = initialize_s3client(logger)
        object = s3_client.get_object(
            Bucket=Config.BUCKET_NAME,
            Key=file_name
        )
        logger.info(f"File opened from S3: {file_name}")
        file_type = file_name.split('.')[-1]
        content = object['Body'].read()
        return content, file_type
    except Exception as e:
        logger.error(f"Error opening file from S3: {e}")
        return None

def download_from_s3(file_name, logger = logger):
    local_path=os.path.join(Config.VIDEO_FOLDER,file_name)
    try:
        s3_client = initialize_s3client(logger)
        s3_client.download_file(Config.BUCKET_NAME, file_name, local_path)
        logger.info(f"File downloaded from S3: {file_name}")
        return local_path
    except Exception as e:
        logger.error(f"Error downloading file from S3: {e}")
        return None
    
# ********************************************* upload / delete files *********************************************

def upload_to_s3(file_content, file_path, file_size = None, logger = logger):
    """ Upload file_content to S3 with a given file_name
    
    args:
        file_content (bytes): binary content of the file
        file_path (str): location to save the file in the s3 bucket
        file_size (int): size of the file
    
    """
    try:
        s3_client = initialize_s3client(logger)
        
        fileNameExists, FileSizeMatch = check_file_exists(file_path, file_size, s3_client)
        if(fileNameExists):
            if(FileSizeMatch):
                logger.info(f"File already exists in S3: {file_path}")
                return None
            else:
                logger.info(f"File already exists in S3 but with different size: {file_path}")
                logger.info(f"Suggesting an alternative file name")
                file_path = file_path.split("/")
                file_name = file_path.pop() # remove name from path
                file_path.append(datetime.now().strftime("%Y%m%d%H%M%S")) # add timestamp
                file_path.append(file_name) # add name
                file_path = "/".join(file_path)
                logger.info(f"New file path: {file_path}")
        
        response = s3_client.put_object(
            Bucket=Config.BUCKET_NAME,
            Key=file_path,
            Body=file_content
        )
        
        logger.info(f"File uploaded to S3: {file_path}")
        return response
    except Exception as e:
        logger.error(f"Error uploading to S3: {e}")
        return None

def delete_file_from_s3(file_name, logger = logger):
    """ Delete file from S3 """
    try:
        s3_client = initialize_s3client(logger)
        response = s3_client.delete_object(
            Bucket=Config.BUCKET_NAME,
            Key=file_name
        )
        logger.info(f"File deleted from S3: {file_name}")
        return response
    except Exception as e:
        logger.error(f"Error deleting file from S3: {e}")
        return None



def Delete_Old_Files_From_S3(age_limit = Config.AGE_LIMIT, logger = logger):
    """ Access S3 bucket and delete files older than age_limit """
    try:
        now = datetime.now(timezone.utc)  # Use UTC time
        files = list_files_in_s3(logger)
        if files is None:
            return None
        for file in files:
            file_name = file['Key']
            file_age = now - file['LastModified']
            if file_age.total_seconds() > age_limit * 60:
                logger.info(f"File deleted: {file_name} with an age of: {file_age}")
                delete_file_from_s3(file_name, logger)
        logger.info("Old files deleted from S3")
    except Exception as e:
        logger.error(f"Error deleting old files from S3: {e}")
        return None


# ********************************************* presigned URL functions *********************************************
def generate_presigned_url_GET(file_path, expires_in = 60, logger = logger):
    """
    Generate a presigned Amazon S3 URL that can be used to perform a GET action.

    :file_path: The path of the file to get or put in the s3 bucket.
    :param expires_in: The number of seconds the presigned URL is valid for.
    :return: The presigned URL.
    """
    try:
        s3_client = initialize_s3client(logger)
        bucket_name = Config.BUCKET_NAME
        key = file_path
        parameters = {"Bucket": bucket_name, "Key": key}
        client_method = "get_object"
        
        url = s3_client.generate_presigned_url(
            ClientMethod=client_method, Params=parameters, ExpiresIn=expires_in
        )
        
    except ClientError:
        logger.exception("Couldn't get a presigned GET URL for client")
        raise
    return url

def generate_presigned_url_POST(file_path, file_size = None, expires_in = 60, logger = logger):
    """
    Generate a presigned Amazon S3 URL that can be used to perform a POST action.

    :file_path: location to save the file in the s3 bucket.
    :param expires_in: The number of seconds the presigned URL is valid for.
    :return: The presigned URL.
    """
    try:
        s3_client = initialize_s3client(logger)
        bucket_name = Config.BUCKET_NAME
        
        logger.info("checking if file exists in S3")
        fileNameExists, FileSizeMatch = check_file_exists(file_path, file_size,  s3_client, logger)
        if(fileNameExists):
            if(FileSizeMatch):
                logger.info(f"File already exists in S3: {file_path}")
                return {"already_exists": "File already exists in S3"}
            else:
                logger.info(f"File already exists in S3 but with different size: {file_path}")
                logger.info(f"Suggesting an alternative file name")
                file_path = file_path.split("/")
                file_name = file_path.pop() # remove name from path
                file_path.append(datetime.now().strftime("%Y%m%d%H%M%S")) # add timestamp
                file_path.append(file_name) # add name
                file_path = "/".join(file_path)
                logger.info(f"New file path: {file_path}")
        
        key = file_path
        response = s3_client.generate_presigned_post(
            Bucket = bucket_name, Key = key, ExpiresIn=expires_in
        )
    except ClientError:
        logger.exception("Couldn't get a presigned POST URL for client")
        raise
    return response

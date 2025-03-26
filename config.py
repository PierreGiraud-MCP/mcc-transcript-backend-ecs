import os
import tempfile
import boto3
import logging
import json

logger = logging.getLogger(__name__)

def get_secrets():
    secret_name = "mcc-transcript"
    region_name = "eu-west-3"
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )
    try:
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_name
        )
        logger.info(f"Secret {secret_name} retrieved")
        return get_secret_value_response['SecretString']
    except Exception as e:  
        logger.error(f"Error retrieving secret {secret_name}: {e}")
        raise e
    

# load env variable from aws secret manager
secrets = get_secrets()
secrets_dict = json.loads(secrets)

class Config:
    #    **************** File system config ****************
    # Base directory of the application
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    
    # Upload file configuration
    ALLOWED_EXTENSIONS={'mp3', 'mp4', 'mpeg', 'mpga', 'm4a', 'wav', 'webm'}
    SUPPORTED_LANGUAGES=["en", "de", "fr", "it", "pt", "hi", "es", "th"]
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB max file size
    CLEANUP_INTERVAL = 24*60 # 1 day = 24*60 minutes
    AGE_LIMIT = 60 # age limit of files: 60 minutes
    
    # File system configuration
    USE_FILE_SYSTEM = secrets_dict.get('USE_FILE_SYSTEM')
    if USE_FILE_SYSTEM == "true":
        TMP_PATH = tempfile.gettempdir()
        VIDEO_FOLDER = os.path.join(TMP_PATH, 'videos')
        os.makedirs(VIDEO_FOLDER, exist_ok=True)   
        
    #    ******************* Logging configuration *******************
    LOG_FOLDER = os.path.join(BASE_DIR, 'logs')
    os.makedirs(LOG_FOLDER, exist_ok=True)
    LOG_FILE = os.path.join(LOG_FOLDER, 'transcript.log')
    LOG_LEVEL = "INFO"
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    LOG_MAX_BYTES = 10485760  # 10MB
    LOG_BACKUP_COUNT = 3
    
    
    #    ******************* Application API configuration *******************
    # API Flask key
    FLASK_SECRET_KEY = secrets_dict.get('FLASK_SECRET_KEY')
    
    # AWS
    AWS_ACCESS_KEY_ID = secrets_dict.get('aws_access_key_id')
    AWS_SECRET_ACESS_KEY = secrets_dict.get('aws_secret_access_key')
    BUCKET_NAME = secrets_dict.get('bucket_name')
    AWS_REGION=secrets_dict.get('region')
    S3_UPLOAD_DIR = "uploads/"
    S3_TRANSCRIPT_DIR = "transcripts/"
    
    # Frontend IP configuration
    IS_DOCKER = secrets_dict.get('IS_DOCKER', False)
    IS_EC2 = secrets_dict.get('IS_EC2', False)
    IS_AMPLIFY = secrets_dict.get('IS_AMPLIFY', False)
    print(f"IS_EC2: {IS_EC2}")
    print(f"IS_DOCKER: {IS_DOCKER}")
    if IS_AMPLIFY == "true":
        FRONTEND_IP = secrets_dict.get('FRONTEND_IP') + ":" + secrets_dict.get("FRONTEND_AMPLIFY_PORT")
    elif IS_EC2 == "true":
        FRONTEND_IP = secrets_dict.get('FRONTEND_IP') + ":" + secrets_dict.get("FRONTEND_PORT")
    elif IS_DOCKER == "true":
        FRONTEND_IP = "http://127.0.0.1:" + secrets_dict.get("FRONTEND_PORT")
    else:
        # Local development
        FRONTEND_IP = "http://localhost:" + secrets_dict.get("FRONTEND_PORT")
    
    
    #    ******************* AI API configuration *******************
    CLIENT_CHOICE = secrets_dict.get('clientChoice','2') # 1: OpenAI, 2: Groq'
    
    # OpenAI configuration
    OPENAI_API_KEY = secrets_dict.get('OPENAI_API_KEY')
    OPENAI_MODEL="whisper-1"
    OPENAI_RESPONSE_FORMAT="verbose_json"
    OPENAI_TEMPERATURE=0.0
    
    # Groq configuration
    GROQ_API_KEY = secrets_dict.get('GROQ_API_KEY')    
    GROQ_MODEL_LIGHT="whisper-large-v3-turbo" # Lighter model, faster, cheaper but less precise
    GROQ_MODEL="whisper-large-v3" # Heavier model, more expensive but better translation
    GROQ_TEMPERATURE=0.0
    GROQ_RESPONSE_FORMAT="verbose_json"
    GROQ_OVERLAP_TIME=10 # seconds

def read_log_file():
    log_file_path = Config.LOG_FILE
    try:
        with open(log_file_path, 'r') as log_file:
            formatted_logs = []
            for line in log_file:
                # Extract and colorize parts of the log line
                parts = line.split(' - ')
                if len(parts) >= 4:
                    timestamp = f'<span style="color: cyan;">{parts[0]}</span>'
                    logger_name = f'<span style="color: lightblue;">{parts[1]}</span>'
                    level = parts[2]
                    message = ' - '.join(parts[3:]).strip()

                    if "ERROR" in level:
                        level = f'<span style="color: red;">{level}</span>'
                        message = f'<span style="color: red;">{message}</span>'
                    elif "INFO" in level:
                        level = f'<span style="color: green;">{level}</span>'
                        message = f'<span style="color: green;">{message}</span>'
                    elif "WARNING" in level:
                        level = f'<span style="color: yellow;">{level}</span>'
                        message = f'<span style="color: yellow;">{message}</span>'

                    formatted_logs.append(f"{timestamp} - {logger_name} - {level} - {message}")
                else:
                    formatted_logs.append(line.strip())  # Fallback for unexpected formats

            return '<br>'.join(formatted_logs)  # Use <br> for HTML line breaks
    except Exception as e:
        logger.error(f"Error reading log file {log_file_path}: {e}")
        return f"Error reading log file: {e}"



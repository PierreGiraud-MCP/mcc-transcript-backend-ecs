import logging
from logging.handlers import RotatingFileHandler
import os
from config import Config

def setup_logger():
    """Configure centralized logging for the application."""
    
    # Create formatter
    formatter = logging.Formatter(Config.LOG_FORMAT)
    
    # Configure file handler
    file_handler = RotatingFileHandler(
        Config.LOG_FILE,
        maxBytes=Config.LOG_MAX_BYTES,
        backupCount=Config.LOG_BACKUP_COUNT
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(Config.LOG_LEVEL)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(Config.LOG_LEVEL)
    
    # Remove any existing handlers to avoid duplicates
    root_logger.handlers = []
    
    # Add the file handler
    root_logger.addHandler(file_handler)
    
    # # Optional: Add console handler for development
    # if os.environ.get('FLASK_ENV') == 'development':
    #     console_handler = logging.StreamHandler()
    #     console_handler.setFormatter(formatter)
    #     root_logger.addHandler(console_handler)
    
    return root_logger 
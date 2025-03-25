import sys
from src.file_utils import *
from config import Config
from src.initiate import initialize_app
from app import app
from src.logger import setup_logger


def main():
    try:
        
        # setting up the app       
        print(f"Python Version: {sys.version}")
        print(f"Flask App: {app}")
        
        initialize_app(app)
        
        # Configure logging
        logger = setup_logger()
        
        # launch cleanup thread
        schedule_cleanup()
        logger.info("Starting Flask application")
        
        # Launching app 
        app.run(host='0.0.0.0', debug=True, port=5001)

    except Exception as e:
        print(f"Error starting Flask app: {e}")

if __name__ == '__main__':
    main()
# McCann Transcript Backend

This folder contains the Flask-based backend for the McCann Transcript application. The backend provides a REST API that handles requests from the frontend, performs data processing, manages business logic, and integrates with external services as needed such as openai's whisper api or groqcloud's speech-to-text api.

## Purpose

The backend serves several key functions:
- **API Endpoints:** Exposes endpoints used by the frontend application to retrieve, update, and manage data.
- **Business Logic & Data Processing:** Handles computations, validations, and data transformations required by the application.
- **(Optional) Authentication & Authorization:** Manages user authentication and access control if needed.
- **External Integrations:** Connects to databases or third-party APIs for additional functionality.

## Manual Launch Instructions

To run the Flask backend manually on your local system, follow these steps:

1. **Navigate to the backend directory:**
   ```bash
   cd backend
   ```

2. **Create a virtual environment (if not already created) and activate it:**

   - **On Windows:**
     ```bash
     python -m venv .venv
     .\venvBackend\Scripts\activate
     ```

   - **On macOS/Linux:**
     ```bash
     python3 -m venv venvBackend
     source venvBackend/bin/activate
     ```

3. **Install the project dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set the necessary environment file:**
    This project requires a `.env` file to store API keys and configuration settings. You'll need to create this file manually since it's not included in version control for security:

    - Create a `.env` file in the `backend` directory:
    ```bash
    touch .env  # On Linux/Mac
    # OR
    type nul > .env  # On Windows
    ```
    
    - Add the following content to your `.env` file:
    ```env
    # Choose API: 1 for OpenAI, 2 for Groq
    clientChoice = 2

    # API Keys (replace with your own keys)
    OPENAI_API_KEY=your_openai_api_key
    GROQ_API_KEY=your_groq_api_key

    You can get API keys from:
    - OpenAI: https://platform.openai.com/api-keys
    - Groq: https://console.groq.com/keys


5. **Launch the Flask application:**
   ```bash
   python run.py
   ```

The backend server will start and, by default, should be accessible at [http://127.0.0.1:5001/](http://127.0.0.1:5001/).


## Additional Notes

- **Development Mode:** this app is currently running in development mode, which enables features like auto-reload and debugging. For production, consider using a production WSGI server like Gunicorn and adjust your configurations accordingly.

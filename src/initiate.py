from flask import Flask
from flask_cors import CORS
from config import Config

def initialize_app(app):
    ip_adresses = [Config.FRONTEND_IP]
    CORS(app, resources={
        r"/api/*": {
            "origins": ip_adresses,
            "methods": ["GET", "POST"],
            "allow_headers": ["Content-Type", "Accept"],
            "supports_credentials": True
        }
    })

    # App configuration
    app.config.from_object(Config)
    app.config['DEBUG'] = True
    return app
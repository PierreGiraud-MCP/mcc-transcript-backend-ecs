from flask import Flask

app = Flask(__name__)
        
# activate API routes    
import src.routes
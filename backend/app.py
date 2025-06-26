from dotenv import load_dotenv
import os

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env')) # Load .env file

from flask import Flask
from flask_cors import CORS
from flask_mysqldb import MySQL
from config import Config
from flask_jwt_extended import JWTManager

app = Flask(__name__)
CORS(app)

# Load configuration
app.config.from_object(Config)

# Initialize MySQL connection
mysql = MySQL(app)
app.extensions['mysql'] = mysql

# Initialize JWT Manager
jwt = JWTManager(app)

# Register Blueprints
# Authentication routes
from routes.auth_routes import auth_bp
app.register_blueprint(auth_bp, url_prefix="/api/auth")

# Jobseeker and Employer routes
from routes.jobseeker_routes import jobseeker_bp
app.register_blueprint(jobseeker_bp, url_prefix="/api")

from routes.employer_routes import employer_bp
app.register_blueprint(employer_bp, url_prefix="/api/employer")

@app.route('/')
def home():
    return {"message": "JobStack API is running"}

if __name__ == "__main__":
    app.run(debug=True)

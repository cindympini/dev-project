from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_socketio import SocketIO

# Database
db = SQLAlchemy()

# Authentication
login_manager = LoginManager()
login_manager.login_view = "login"   # Redirects unauthorized users to login
login_manager.login_message = "Please log in to access this page."

# Real-time (SocketIO)
socketio = SocketIO(cors_allowed_origins="*")
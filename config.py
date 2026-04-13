import os

class Config:
    SECRET_KEY = "super-secret-key"
    SQLALCHEMY_DATABASE_URI = "sqlite:///devhub.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
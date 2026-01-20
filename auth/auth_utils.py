from flask import session

def require_login():
    return "user" in session

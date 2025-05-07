from app import db
from app.models import User
from flask_login import login_user, logout_user, current_user

def create_user(username, password):
    """Creates a new user or returns existing one if username matches."""
    user = User.query.filter_by(username=username).first()
    if user:
        # In this specific project, initial password is same as username.
        # If user exists, we could either update password (if logic allows) or signal existing user.
        # For this project, if user exists, we assume it was created before, possibly with this default.
        # No automatic re-set of password if user exists.
        return user, False # Existing user
    
    new_user = User(username=username)
    new_user.set_password(password)
    db.session.add(new_user)
    try:
        db.session.commit()
        return new_user, True # New user created
    except Exception as e:
        db.session.rollback()
        # Log error e
        return None, False

def authenticate_user(username, password):
    """Authenticates a user and logs them in."""
    user = User.query.filter_by(username=username).first()
    if user and user.check_password(password):
        login_user(user, remember=True) # Can make remember_me a parameter
        return user
    return None

def change_user_password(user, current_password, new_password):
    """Changes the password for a user."""
    if user.check_password(current_password):
        user.set_password(new_password)
        db.session.add(user)
        try:
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            # Log error e
            return False
    return False

def logout_current_user():
    """Logs out the current user."""
    logout_user() 
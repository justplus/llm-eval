from app import db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(UserMixin, db.Model):
    __tablename__ = 'users' # Explicit table name
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    ai_models = db.relationship('AIModel', back_populates='owner', lazy='dynamic', cascade="all, delete-orphan")
    chat_sessions = db.relationship('ChatSession', back_populates='user', lazy='dynamic', cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'

class AIModel(db.Model):
    __tablename__ = 'ai_models' # Explicit table name
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True) # Null for system models (owned by no specific user)
    
    display_name = db.Column(db.String(100), nullable=False)
    model_type = db.Column(db.String(50), nullable=False, default='openai_compatible') 
    api_base_url = db.Column(db.String(255), nullable=False)
    model_identifier = db.Column(db.String(100), nullable=False)
    encrypted_api_key = db.Column(db.String(512), nullable=True)
    provider_name = db.Column(db.String(100), nullable=True)
    is_system_model = db.Column(db.Boolean, default=False, nullable=False)
    system_prompt = db.Column(db.Text, nullable=True, default="You are a helpful assistant.")
    default_temperature = db.Column(db.Float, nullable=True, default=0.7)
    notes = db.Column(db.Text, nullable=True)
    is_validated = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    owner = db.relationship('User', back_populates='ai_models')
    chat_messages = db.relationship('ChatMessage', back_populates='ai_model', lazy='dynamic')

    def __repr__(self):
        return f'<AIModel {self.display_name} ({self.model_identifier})>'

class ChatSession(db.Model):
    __tablename__ = 'chat_sessions' # Explicit table name
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    session_name = db.Column(db.String(150), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    config_data = db.Column(db.JSON, nullable=True) # 存储会话的配置数据，例如模型配置

    user = db.relationship('User', back_populates='chat_sessions')
    messages = db.relationship('ChatMessage', back_populates='session', lazy='dynamic', cascade="all, delete-orphan")

    def __repr__(self):
        return f'<ChatSession {self.id} by User {self.user_id}>'

class ChatMessage(db.Model):
    __tablename__ = 'chat_messages' # Explicit table name
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('chat_sessions.id'), nullable=False)
    model_id = db.Column(db.Integer, db.ForeignKey('ai_models.id'), nullable=True) 
    role = db.Column(db.String(20), nullable=False)  # 'user', 'assistant', 'system'
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    settings_snapshot = db.Column(db.JSON, nullable=True) 

    session = db.relationship('ChatSession', back_populates='messages')
    ai_model = db.relationship('AIModel', back_populates='chat_messages')

    def __repr__(self):
        return f'<ChatMessage {self.id} in Session {self.session_id} by {self.role}>' 
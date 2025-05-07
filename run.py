from flask import Flask
from app import create_app, db
from app.models import User, AIModel, ChatSession, ChatMessage

app = create_app()

@app.shell_context_processor
def make_shell_context():
    return {'db': db, 'User': User, 'AIModel': AIModel, 'ChatSession': ChatSession, 'ChatMessage': ChatMessage}

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0') 
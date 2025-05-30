from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user

bp = Blueprint('main', __name__)

@bp.route('/')
@bp.route('/index')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('auth.login'))

@bp.route('/dashboard')
@login_required
def dashboard():
    # This will be the main page after login, showing models, chat options, etc.
    # For now, a simple placeholder.
    print('------')
    return render_template('dashboard.html', title='仪表盘') 
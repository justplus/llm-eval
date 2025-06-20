from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from app.forms import LoginForm, ChangePasswordForm
from app.models import User
from app import db # Direct db import for user creation initially, can be refactored to service
from app.services import user_service

bp = Blueprint('auth', __name__)

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard')) # or main.index
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        # Per requirements: "初始密码跟账号一样"
        if user is None:
            # User does not exist, create them with password same as username
            user, created = user_service.create_user(form.username.data, form.username.data)
            if created:
                flash('新用户已创建，初始密码与用户名相同。请及时修改密码。', 'info')
                user_service.authenticate_user(form.username.data, form.username.data, form.remember_me.data) # 登录新用户
                return redirect(url_for('main.dashboard')) # Or to change_password page
            elif user is None: # Creation failed
                flash('创建用户时发生错误，请重试。', 'danger')
                return render_template('auth/login.html', title='登录', form=form)
        
        # User exists or was just created, try to authenticate
        authenticated_user = user_service.authenticate_user(form.username.data, form.password.data, form.remember_me.data)
        if authenticated_user:
            next_page = request.args.get('next')
            if not next_page or url_for(next_page.lstrip('/')) == url_for('main.index'): # Prevent open redirect
                next_page = url_for('main.dashboard') 
            return redirect(next_page)
        else:
            flash('用户名或密码无效。', 'danger')
    return render_template('auth/login.html', title='登录', form=form)

@bp.route('/logout')
@login_required
def logout():
    user_service.logout_current_user()
    return redirect(url_for('auth.login'))

@bp.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if user_service.change_user_password(current_user, form.current_password.data, form.new_password.data):
            flash('密码已成功修改。', 'success')
            return redirect(url_for('main.dashboard')) # Or wherever appropriate
        else:
            flash('当前密码不正确或更新失败，请重试。', 'danger')
    return render_template('auth/change_password.html', title='修改密码', form=form)

@bp.route('/clear_session')
def clear_session():
    """清理会话数据的路由，用于解决会话损坏问题"""
    session.clear()
    flash('会话已清理，请重新登录。', 'info')
    return redirect(url_for('auth.login')) 
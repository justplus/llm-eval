from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, TextAreaField, FloatField
from wtforms.validators import DataRequired, Length, EqualTo, Optional, URL, NumberRange

class LoginForm(FlaskForm):
    username = StringField('用户名', validators=[DataRequired(), Length(min=3, max=64)])
    password = PasswordField('密码', validators=[DataRequired()])
    remember_me = BooleanField('记住我')
    submit = SubmitField('登录')

class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('当前密码', validators=[DataRequired()])
    new_password = PasswordField('新密码', validators=[DataRequired(), Length(min=6, max=128)])
    confirm_new_password = PasswordField('确认新密码', 
                                     validators=[DataRequired(), EqualTo('new_password', message='两次输入的新密码必须一致。')])
    submit = SubmitField('修改密码')

class AIModelForm(FlaskForm):
    display_name = StringField('模型显示名称', validators=[DataRequired(), Length(max=100)])
    api_base_url = StringField('API Base URL', validators=[DataRequired(), URL(), Length(max=255)])
    model_identifier = StringField('模型标识 (API调用名)', validators=[DataRequired(), Length(max=100)])
    api_key = PasswordField('API Key (可选，如需更新或设置请填写)', validators=[Optional(), Length(max=500)]) # Increased length for safety
    provider_name = StringField('提供商名称 (可选)', validators=[Optional(), Length(max=100)])
    system_prompt = TextAreaField('默认系统提示 (可选)', validators=[Optional()])
    default_temperature = FloatField('默认Temperature (0-2, 可选)', validators=[Optional(), NumberRange(min=0.0, max=2.0)])
    notes = TextAreaField('备注 (可选)', validators=[Optional()])
    submit = SubmitField('保存模型') 
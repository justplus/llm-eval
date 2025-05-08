from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, PasswordField, BooleanField, SubmitField, TextAreaField, FloatField, SelectField, SelectMultipleField
from wtforms.validators import DataRequired, Length, EqualTo, Optional, URL, NumberRange
from wtforms.widgets import ListWidget, CheckboxInput

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

class CustomDatasetForm(FlaskForm):
    name = StringField('数据集名称', validators=[DataRequired(), Length(max=200)])
    description = TextAreaField('描述', validators=[Optional(), Length(max=5000)])
    categories = SelectMultipleField('测评方向', 
                                   validators=[Optional()], 
                                   widget=ListWidget(prefix_label=False),
                                   option_widget=CheckboxInput(),
                                   description="选择一个或多个测评方向")
    publish_date = StringField('发布时间', validators=[Optional(), Length(max=50)])
    source = StringField('来源', validators=[Optional(), Length(max=100)])
    dataset_file = FileField('数据集文件上传', 
                             validators=[Optional(), FileAllowed(['zip', 'csv', 'json', 'txt', 'jsonl'], '仅允许上传 ZIP, CSV, JSON, TXT, JSONL 文件!')],
                             description="上传数据集的压缩文件或数据文件。")
    sample_data_json = TextAreaField('样例数据 (JSON格式, 最多约50条)', 
                                   validators=[Optional()], 
                                   description='请粘贴JSON数组格式的样例数据，例如：[{"question": "Q1", "answer": "A1"}, {"question": "Q2", "answer": "A2"}]')
    visibility = SelectField('可见性', 
                             choices=[('公开', '公开'), ('不公开', '不公开')], 
                             validators=[DataRequired()],
                             default='公开')
    submit = SubmitField('保存数据集') 
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import AIModel
from app.forms import AIModelForm
from app.services import model_service

bp = Blueprint('models', __name__, url_prefix='/models')

@bp.route('/')
@login_required
def list_models():
    models = model_service.get_all_models_for_user(current_user)
    # Pass decrypted keys for display/information purposes if needed, be cautious with this.
    # For now, we won't pass decrypted keys to the list view for security.
    return render_template('models/list_models.html', models=models, title="模型管理")

@bp.route('/new', methods=['GET', 'POST'])
@login_required
def create_model():
    form = AIModelForm()
    if form.validate_on_submit():
        # model_type is not in the form directly, defaults in service or can be added
        model_data = {
            "display_name": form.display_name.data,
            "api_base_url": form.api_base_url.data,
            "model_identifier": form.model_identifier.data,
            "api_key": form.api_key.data, # Will be encrypted by the service
            "provider_name": form.provider_name.data,
            "system_prompt": form.system_prompt.data,
            "default_temperature": form.default_temperature.data,
            "notes": form.notes.data,
            "model_type": "openai_compatible" # Or get from form if added
        }
        new_model = model_service.create_user_model(model_data, current_user)
        if new_model:
            flash(f"模型 ‘{new_model.display_name}’ 已成功创建。", 'success')
            # Optionally, validate the new model immediately
            # success, message = model_service.validate_model_connectivity(new_model)
            # flash(message, 'success' if success else 'warning')
            return redirect(url_for('models.list_models'))
        else:
            flash('创建模型失败，请检查您的输入或联系管理员。', 'error')
    return render_template('models/model_form.html', form=form, title="添加新模型", form_title="创建新的自定义AI模型", submit_button_text="创建模型")

@bp.route('/<int:model_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_model(model_id):
    model = model_service.get_model_by_id_for_user(model_id, current_user)
    if not model or model.is_system_model:
        flash('无法编辑此模型或模型不存在。', 'error')
        return redirect(url_for('models.list_models'))

    # 在编辑时回填API Key用于显示和修改
    form = AIModelForm(obj=model)
    if not form.is_submitted(): # GET请求时回填API Key
        # 获取解密后的API Key用于回填
        decrypted_key = model_service.get_decrypted_api_key(model)
        form.api_key.data = decrypted_key if decrypted_key and decrypted_key != "[decryption_error]" else ""

    if form.validate_on_submit():
        model_data = {
            "display_name": form.display_name.data,
            "api_base_url": form.api_base_url.data,
            "model_identifier": form.model_identifier.data,
            "provider_name": form.provider_name.data,
            "system_prompt": form.system_prompt.data,
            "default_temperature": form.default_temperature.data,
            "notes": form.notes.data,
            "model_type": model.model_type, # Keep original type or allow change via form
            "api_key": form.api_key.data # 始终包含API Key，因为现在会回填显示
        }
        if model_service.update_user_model(model, model_data):
            flash(f"模型 ‘{model.display_name}’ 已成功更新。", 'success')
            return redirect(url_for('models.list_models'))
        else:
            flash('更新模型失败。', 'error')
    else: # Populate form for GET request
        form.display_name.data = model.display_name
        form.api_base_url.data = model.api_base_url
        form.model_identifier.data = model.model_identifier
        form.provider_name.data = model.provider_name
        form.system_prompt.data = model.system_prompt
        form.default_temperature.data = model.default_temperature
        form.notes.data = model.notes
        # API key field is intentionally left blank for security. User must re-enter if changing.

    return render_template('models/model_form.html', form=form, model=model, title=f"编辑模型: {model.display_name}", form_title=f"编辑模型: {model.display_name}", submit_button_text="保存更改")

@bp.route('/<int:model_id>/delete', methods=['POST']) # POST for safety
@login_required
def delete_model(model_id):
    model = model_service.get_model_by_id_for_user(model_id, current_user)
    if not model or model.is_system_model:
        flash('无法删除此模型或模型不存在。', 'error')
        return redirect(url_for('models.list_models'))
    
    display_name = model.display_name
    if model_service.delete_user_model(model):
        flash(f"模型 ‘{display_name}’ 已成功删除。", 'success')
    else:
        flash(f"删除模型 ‘{display_name}’ 失败。", 'error')
    return redirect(url_for('models.list_models'))

@bp.route('/<int:model_id>/validate', methods=['POST'])
@login_required
def validate_model(model_id):
    model = model_service.get_model_by_id_for_user(model_id, current_user)
    if not model:
        flash('模型不存在。', 'error')
        return redirect(url_for('models.list_models'))

    # For system models, API key might come from global config
    # For user models, it's decrypted from db
    # The validation service should handle this logic

    success, message = model_service.validate_model_connectivity(model)
    if success:
        flash(f"模型 ‘{model.display_name}’ 验证成功: {message}", 'success')
    else:
        flash(f"模型 ‘{model.display_name}’ 验证失败: {message}", 'warning')
    return redirect(url_for('models.list_models')) 
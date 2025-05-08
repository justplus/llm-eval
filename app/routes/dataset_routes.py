from flask import Blueprint, render_template, request, current_app, flash, redirect, url_for # Added flash, redirect, url_for
from app import db # 数据库实例
from app.models import SystemDataset, DatasetCategory # 数据模型
from app.forms import CustomDatasetForm # Import the new form
import json # For parsing sample_data_json
import os # For os.path.join
from werkzeug.utils import secure_filename # For secure filenames

# 创建一个名为 'datasets' 的蓝图
bp = Blueprint('datasets', __name__, url_prefix='/datasets')

@bp.route('/system')
def system_datasets_list():
    """
    显示系统内置的数据集列表，支持按分类筛选。
    """
    selected_category_name = request.args.get('category', '全部') # 默认为'全部'
    
    all_db_categories = DatasetCategory.query.order_by(DatasetCategory.name).all()
    
    query = SystemDataset.query
    
    if selected_category_name != '全部' and selected_category_name:
        query = query.join(SystemDataset.categories).filter(DatasetCategory.name == selected_category_name)
        
    datasets_from_db = query.order_by(SystemDataset.name).all()
    
    return render_template(
        'datasets/system_datasets.html', 
        datasets=datasets_from_db, 
        all_categories=all_db_categories,
        selected_category=selected_category_name
    ) 

@bp.route('/custom/add', methods=['GET', 'POST'])
# @login_required # Consider adding login_required if not already applied to the blueprint
def add_custom_dataset():
    form = CustomDatasetForm()
    # Populate category choices dynamically
    form.categories.choices = [(cat.id, cat.name) for cat in DatasetCategory.query.order_by('name').all()]

    if form.validate_on_submit():
        try:
            # Process categories from selected IDs
            category_objects = []
            if form.categories.data:
                for cat_id_str in form.categories.data:
                    try:
                        cat_id = int(cat_id_str)
                        category = db.session.get(DatasetCategory, cat_id) # More direct way to get by PK with SQLAlchemy 2.0+
                        if category:
                            category_objects.append(category)
                    except ValueError:
                        flash(f'无效的分类ID: {cat_id_str}', 'warning')
            
            # Process sample data
            sample_data_list = None
            if form.sample_data_json.data:
                try:
                    sample_data_list = json.loads(form.sample_data_json.data)
                    if not isinstance(sample_data_list, list):
                        flash('样例数据必须是有效的JSON数组格式。', 'error')
                        # Re-render to show error and keep form data
                        return render_template('datasets/add_custom_dataset.html', title='添加自定义数据集', form=form)
                except json.JSONDecodeError:
                    flash('样例数据JSON格式无效，请检查。', 'error')
                    form.sample_data_json.errors.append("无效的JSON格式。")
                    return render_template('datasets/add_custom_dataset.html', title='添加自定义数据集', form=form)

            # Handle file upload
            uploaded_filename = None
            if form.dataset_file.data:
                file = form.dataset_file.data
                filename = secure_filename(file.filename)
                if filename: # Ensure filename is not empty after secure_filename
                    upload_folder = current_app.config.get('DATASET_UPLOAD_FOLDER', os.path.join(current_app.root_path, 'uploads', 'datasets'))
                    if not os.path.exists(upload_folder):
                        os.makedirs(upload_folder, exist_ok=True)
                    file_path = os.path.join(upload_folder, filename)
                    file.save(file_path)
                    uploaded_filename = filename # Store just the filename, or a relative path
                else:
                    flash('上传的文件名无效。', 'warning')

            new_dataset = SystemDataset(
                name=form.name.data,
                description=form.description.data,
                publish_date=form.publish_date.data,
                source=form.source.data,
                download_url=uploaded_filename, # Store filename of uploaded dataset file
                sample_data=sample_data_list,
                dataset_type='自建',
                visibility=form.visibility.data,
                categories=category_objects
            )
            db.session.add(new_dataset)
            db.session.commit()
            flash(f'自定义数据集 " {new_dataset.name} " 已成功添加!', 'success')
            return redirect(url_for('datasets.system_datasets_list'))
        except ValueError as ve:
            current_app.logger.error(f"Error adding custom dataset: {ve}")
            flash(f'添加数据集失败: {ve}', 'error')
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error adding custom dataset: {e}")
            flash(f'添加数据集时发生错误，请稍后重试或联系管理员。', 'error')
            
    # For GET request or if form validation failed, re-render with choices populated
    if not form.categories.choices: # Ensure choices are set if validation failed and it's a POST
        form.categories.choices = [(cat.id, cat.name) for cat in DatasetCategory.query.order_by('name').all()]
        
    return render_template('datasets/add_custom_dataset.html', title='添加自定义数据集', form=form) 
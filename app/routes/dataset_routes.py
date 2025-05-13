from flask import Blueprint, render_template, request, current_app, flash, redirect, url_for, jsonify # Added jsonify
from app import db # 数据库实例
from app.models import SystemDataset, DatasetCategory # 数据模型
from app.forms import CustomDatasetForm # Import the new form
from app.services.dataset_service import DatasetService # 导入数据集服务
import json # For parsing sample_data_json
import os # For os.path.join
from werkzeug.utils import secure_filename # For secure filenames
import math # 用于分页计算

# 创建一个名为 'datasets' 的蓝图
bp = Blueprint('datasets', __name__, url_prefix='/datasets')

@bp.route('/system')
def system_datasets_list():
    """
    显示系统内置的数据集列表，支持按分类筛选。
    默认只显示已激活的数据集，通过show_all参数可显示所有数据集。
    """
    selected_category_name = request.args.get('category', '全部') # 默认为'全部'
    show_all = request.args.get('show_all', '0') == '1' # 默认不显示所有数据集
    
    all_db_categories = DatasetCategory.query.order_by(DatasetCategory.name).all()
    
    query = SystemDataset.query
    
    # 如果不显示所有数据集，则只返回已激活的数据集
    if not show_all:
        query = query.filter(SystemDataset.is_active == True)
    
    if selected_category_name != '全部' and selected_category_name:
        query = query.join(SystemDataset.categories).filter(DatasetCategory.name == selected_category_name)
        
    datasets_from_db = query.order_by(SystemDataset.name).all()
    
    return render_template(
        'datasets/system_datasets.html', 
        datasets=datasets_from_db, 
        all_categories=all_db_categories,
        selected_category=selected_category_name,
        show_all=show_all
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
                    dataset_info_data = json.loads(form.sample_data_json.data)
                    # 不再检查是否为列表，因为dataset_info结构是一个对象
                except json.JSONDecodeError:
                    flash('数据集结构信息JSON格式无效，请检查。', 'error')
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
                dataset_info=dataset_info_data,
                dataset_type='自建',
                visibility=form.visibility.data,
                format=form.format.data,
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

@bp.route('/api/dataset/<int:dataset_id>/data')
def api_dataset_data(dataset_id):
    """
    API端点：异步获取数据集预览数据
    """
    # 获取数据集信息
    dataset = SystemDataset.query.get_or_404(dataset_id)
    
    # 获取筛选参数
    subset = request.args.get('subset', '')
    split = request.args.get('split', '')
    page = request.args.get('page', 1, type=int)
    per_page = 20  # 每页显示20条数据
    
    # 使用DatasetService获取数据集数据
    data, total_items = DatasetService.get_dataset_data(
        dataset.dataset_info or {}, 
        subset, 
        split, 
        dataset.download_url,
        page, 
        per_page
    )
    
    # 计算总页数
    total_pages = math.ceil(total_items / per_page) if total_items > 0 else 0
    
    # 计算分页范围
    start_page = max(1, page - 2)
    end_page = min(total_pages + 1, page + 3) if total_pages > 0 else 1
    page_range = list(range(start_page, end_page))
    
    return jsonify({
        'data': data,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total_items': total_items,
            'total_pages': total_pages,
            'page_range': page_range
        }
    })

@bp.route('/preview/<int:dataset_id>')
def preview_dataset(dataset_id):
    """
    预览数据集内容，支持筛选子数据集和用途。
    使用异步加载方式获取数据集数据。
    """
    # 获取数据集信息
    dataset = SystemDataset.query.get_or_404(dataset_id)
    
    # 获取筛选参数
    subset = request.args.get('subset', '')
    split = request.args.get('split', '')
    page = request.args.get('page', 1, type=int)
    
    # 使用DatasetService获取数据集结构信息
    subsets, splits_by_subset = DatasetService.get_dataset_structure(dataset.dataset_info or {})
    
    # 调试日志
    current_app.logger.info(f"数据集结构: subsets={subsets}, splits_by_subset={splits_by_subset}")
    
    # 如果未指定子数据集但有可用的子数据集，则使用第一个
    if not subset and subsets:
        subset = subsets[0]
    
    # 如果未指定split但当前子数据集有可用的split，则使用第一个
    available_splits = splits_by_subset.get(subset, [])
    if not split and available_splits:
        split = available_splits[0]
    
    # 调试日志
    current_app.logger.info(f"当前选择: subset={subset}, split={split}")
    current_app.logger.info(f"current_subset在splits_by_subset中: {subset in splits_by_subset}")
    
    # 渲染预览页面 - 不再直接加载数据，改为前端异步加载
    return render_template(
        'datasets/preview_dataset.html',
        dataset=dataset,
        subsets=subsets,
        splits_by_subset=splits_by_subset,
        current_subset=subset,
        current_split=split,
        page=page
    ) 

@bp.route('/api/dataset/<int:dataset_id>/toggle_active', methods=['POST'])
def toggle_dataset_active(dataset_id):
    """
    API端点：切换数据集的启用/禁用状态
    """
    dataset = SystemDataset.query.get_or_404(dataset_id)
    
    # 切换状态
    dataset.is_active = not dataset.is_active
    
    try:
        db.session.commit()
        status = "启用" if dataset.is_active else "禁用"
        return jsonify({
            'success': True,
            'is_active': dataset.is_active,
            'message': f'数据集 "{dataset.name}" 已{status}'
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"切换数据集状态失败: {e}")
        return jsonify({
            'success': False,
            'message': f'操作失败: {str(e)}'
        }), 500 
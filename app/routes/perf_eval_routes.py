from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from app import db
from app.models import PerformanceEvalTask, AIModel, SystemDataset
from app.forms import PerformanceEvalForm
from app.services.perf_service import PerformanceEvaluationService
from sqlalchemy import and_, or_

perf_eval_bp = Blueprint('perf_eval', __name__, url_prefix='/perf_eval')

@perf_eval_bp.route('/', methods=['GET'])
@login_required
def index():
    """性能评估首页"""
    return render_template('perf_eval/index.html', title="性能评估")

@perf_eval_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """创建性能评估任务"""
    form = PerformanceEvalForm()
    
    # 获取已注册的模型用于选择 - 修复显示问题：使用display_name而不是model_identifier
    user_models = [(m.id, m.display_name) for m in AIModel.query.filter_by(user_id=current_user.id, is_system_model=False).all()]
    
    # 获取可用的数据集
    # 权限控制：自己创建的自建数据集 + 别人公开的自建数据集
    available_datasets = [
        (d.id, d.name) for d in SystemDataset.query.filter(
            and_(
                SystemDataset.is_active == True,
                SystemDataset.dataset_type == '自建',
                or_(
                    # 自己创建的自建数据集（无论是否公开）
                    SystemDataset.source == current_user.username,
                    # 别人创建的公开自建数据集
                    and_(
                        SystemDataset.source != current_user.username,
                        SystemDataset.visibility == '公开'
                    )
                )
            )
        ).all()
    ]

    form.model_name.choices = user_models
    form.dataset_name.choices = available_datasets
    
    if form.validate_on_submit():
        try:
            # 创建性能评估任务
            task = PerformanceEvaluationService.create_performance_eval_task(
                model_id=form.model_name.data,
                dataset_id=form.dataset_name.data,
                concurrency=form.concurrency.data,
                num_requests=form.num_requests.data,
                user_id=current_user.id
            )
            
            if task:
                # 启动评估任务
                PerformanceEvaluationService.run_performance_evaluation(task.id, form.model_name.data, form.dataset_name.data, form.concurrency.data, form.num_requests.data)
                flash(f'性能评估任务已创建并开始执行，任务ID: {task.id}', 'success')
                return redirect(url_for('perf_eval.results', task_id=task.id, source='create'))
            else:
                flash('创建性能评估任务失败，请检查输入参数', 'error')
                
        except Exception as e:
            current_app.logger.error(f"创建性能评估任务时发生错误: {str(e)}")
            flash(f'创建任务时发生错误: {str(e)}', 'error')
    
    return render_template('perf_eval/create.html', 
                         form=form, 
                         title="创建性能评估任务",
                         models=user_models,
                         datasets=available_datasets)

@perf_eval_bp.route('/history')
@login_required
def history():
    """性能评估任务历史"""
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    tasks, total = PerformanceEvaluationService.get_all_tasks(user_id=current_user.id, page=page, per_page=per_page)
    return render_template('perf_eval/history.html', 
                         history_tasks=tasks, 
                         total=total,
                         page=page,
                         per_page=per_page,
                         title="性能评估历史")

@perf_eval_bp.route('/results/<int:task_id>')
@login_required
def results(task_id):
    """查看性能评估结果"""
    task = PerformanceEvaluationService.get_task_by_id(task_id, user_id=current_user.id)
    if not task:
        flash('任务不存在或您没有权限查看', 'error')
        return redirect(url_for('perf_eval.history'))
    
    source = request.args.get('source', 'history')
    return render_template('perf_eval/results.html', 
                         task=task, 
                         source=source,
                         title=f"性能评估结果 - 任务 {task_id}")

@perf_eval_bp.route('/delete/<int:task_id>', methods=['POST'])
@login_required
def delete_task(task_id):
    """删除性能评估任务"""
    # 获取当前页码，默认为1
    current_page = request.args.get('page', 1, type=int)
    
    success = PerformanceEvaluationService.delete_task(task_id, user_id=current_user.id)
    
    if success:
        flash('任务删除成功', 'success')
        
        # 检查删除后当前页是否为空，如果为空且不是第1页，则重定向到上一页
        tasks, total = PerformanceEvaluationService.get_all_tasks(user_id=current_user.id, page=current_page, per_page=10)
        if not tasks and current_page > 1:
            # 当前页为空且不是第1页，重定向到上一页
            return redirect(url_for('perf_eval.history', page=current_page-1))
    else:
        flash('任务删除失败或任务不存在', 'error')
    
    # 重定向到当前页
    return redirect(url_for('perf_eval.history', page=current_page))
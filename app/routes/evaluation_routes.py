from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, current_app, abort, make_response
from flask_login import login_required, current_user
from app import db
from app.models import AIModel, Dataset, ModelEvaluation, ModelEvaluationResult, ModelEvaluationDataset
from app.services.evaluation_service import EvaluationService
import json
from math import ceil # 用于分页计算
from sqlalchemy import or_, and_
from datetime import datetime

bp = Blueprint('evaluations', __name__, url_prefix='/evaluations')

@bp.route('/')
@login_required
def evaluations_list():
    """模型评估历史列表页面"""
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    evaluations, total = EvaluationService.get_evaluations_for_user(current_user.id, page, per_page)
    
    # 计算总页数
    total_pages = (total + per_page - 1) // per_page if total > 0 else 0
    
    return render_template(
        'evaluations/evaluations_list.html',
        evaluations=evaluations,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
        title="模型评估历史"
    )

@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_evaluation():
    """创建模型评估页面"""
    if request.method == 'GET':
        # 获取用户可用的自定义模型列表 (被评估模型)
        # 移除is_validated限制，允许用户评估自己的所有自定义模型
        custom_models = AIModel.query.filter_by(is_system_model=False).all()
        
        # 调试信息
        current_app.logger.info(f"用户 {current_user.username} 的自定义模型数量: {len(custom_models)}")
        for model in custom_models:
            current_app.logger.info(f"模型: {model.display_name}, 验证状态: {model.is_validated}")
        
        # 获取系统内置模型列表 (裁判模型)
        system_models = AIModel.query.filter_by(is_system_model=True).all()
        current_app.logger.info(f"系统模型数量: {len(system_models)}")

        all_models = AIModel.query.all()
        
        # 获取已启用的数据集列表 - 修复权限问题
        # 1. 自己创建的所有数据集（无论是否公开）
        # 2. 别人创建的公开数据集
        datasets = Dataset.query.filter(
            Dataset.is_active == True
        ).filter(
            or_(
                # 自己创建的所有数据集
                Dataset.source == current_user.username,
                # 别人创建的公开数据集
                and_(
                    Dataset.source != current_user.username,
                    Dataset.visibility == '公开'
                ),
                # 系统数据集（source为空或为'系统'）
                or_(
                    Dataset.source.is_(None),
                    Dataset.source == '系统'
                )
            )
        ).order_by(Dataset.name).all()
        
        return render_template(
            'evaluations/create_evaluation.html',
            custom_models=custom_models,
            system_models=system_models,
            all_models=all_models,
            datasets=datasets,
            title="创建模型评估"
        )
    
    elif request.method == 'POST':
        try:
            # 获取表单数据
            model_id = request.form.get('model_id', type=int)
            judge_model_id = request.form.get('judge_model_id', type=int, default=None)
            temperature = request.form.get('temperature', type=float, default=0.7)
            max_tokens = request.form.get('max_tokens', type=int, default=2048)
            evaluation_name = request.form.get('evaluation_name', '')
            limit = request.form.get('limit', type=int, default=None)
            
            # 验证模型权限
            target_model = AIModel.query.get(model_id)
            judge_model = None if judge_model_id is None else AIModel.query.get(judge_model_id)
            
            if not target_model:
                flash('所选模型不存在。', 'error')
                return redirect(url_for('evaluations.create_evaluation'))
            
            # 检查用户对被评估模型的权限 (必须是用户的自定义模型)
            if target_model.is_system_model or target_model.user_id != current_user.id:
                flash('您只能选择自己的自定义模型进行评估。', 'error')
                return redirect(url_for('evaluations.create_evaluation'))
                
            # 获取选择的数据集 (不再需要子集和分割)
            datasets_data = []
            selected_dataset_ids = []
            for key in request.form:
                if key.startswith('dataset_'):
                    dataset_id = int(key.split('_')[1])
                    selected_dataset_ids.append(dataset_id)
            
            if not selected_dataset_ids:
                flash('请至少选择一个数据集。', 'error')
                return redirect(url_for('evaluations.create_evaluation'))
            
            # 验证所选数据集是否存在且已启用
            for ds_id in selected_dataset_ids:
                dataset = Dataset.query.filter_by(id=ds_id, is_active=True).first()
                if not dataset:
                    flash(f'选择的数据集ID {ds_id} 无效或未启用。', 'error')
                    return redirect(url_for('evaluations.create_evaluation'))
                datasets_data.append({'dataset_id': ds_id}) # 只传递 dataset_id
            
            # 创建评估任务
            evaluation = EvaluationService.create_evaluation(
                user_id=current_user.id,
                model_id=model_id,
                judge_model_id=judge_model_id,
                datasets=datasets_data, # 传递简化的数据集信息
                temperature=temperature,
                max_tokens=max_tokens,
                name=evaluation_name,
                limit=limit
            )
            
            if evaluation:
                flash('评估任务创建成功，正在后台处理...', 'success')
                return redirect(url_for('evaluations.view_evaluation', evaluation_id=evaluation.id))
            else:
                flash('创建评估任务失败。', 'error')
                return redirect(url_for('evaluations.create_evaluation'))
            
        except Exception as e:
            current_app.logger.error(f"创建评估任务失败: {str(e)}")
            flash(f'创建评估任务时发生错误: {str(e)}', 'error')
            return redirect(url_for('evaluations.create_evaluation'))

@bp.route('/<int:evaluation_id>')
@login_required
def view_evaluation(evaluation_id):
    """查看评估详情页面"""
    evaluation = EvaluationService.get_evaluation_by_id(evaluation_id, current_user.id)
    
    if not evaluation:
        flash('评估不存在或您无权访问。', 'error')
        return redirect(url_for('evaluations.evaluations_list'))
    
    # 获取评估关联的模型
    model = AIModel.query.get(evaluation.model_id)
    judge_model = None if evaluation.judge_model_id is None else AIModel.query.get(evaluation.judge_model_id)
    
    # 获取评估数据集信息 (不再包含子集和分割)
    datasets_info = []
    for eval_dataset_assoc in evaluation.datasets:
        dataset = Dataset.query.get(eval_dataset_assoc.dataset_id)
        if dataset:
            datasets_info.append({
                'dataset': dataset,
                'subset': eval_dataset_assoc.subset or '默认', # 显示默认或空
                'split': eval_dataset_assoc.split or '默认'   # 显示默认或空
            })
    
    # 获取评估结果
    page = request.args.get('page', 1, type=int)
    per_page = 10
    results, total_results = EvaluationService.get_evaluation_results(evaluation_id, current_user.id, page, per_page)
    
    # 计算总页数
    total_pages = (total_results + per_page - 1) // per_page if total_results > 0 else 0
    
    return render_template(
        'evaluations/view_evaluation.html',
        evaluation=evaluation,
        model=model,
        judge_model=judge_model,
        datasets_info=datasets_info,
        results=results,
        total_results=total_results,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
        title=f"评估详情: {evaluation.name}"
    )

@bp.route('/api/status/<int:evaluation_id>')
@login_required
def api_evaluation_status(evaluation_id):
    """API端点: 获取评估任务状态"""
    evaluation = EvaluationService.get_evaluation_by_id(evaluation_id, current_user.id)
    
    if not evaluation:
        return jsonify({"error": "评估不存在或您无权访问"}), 404
    
    return jsonify({
        "id": evaluation.id,
        "status": evaluation.status,
        "created_at": evaluation.created_at.isoformat(),
        "completed_at": evaluation.completed_at.isoformat() if evaluation.completed_at else None,
        "result_summary": evaluation.result_summary
    })

@bp.route('/<int:evaluation_id>/delete', methods=['POST'])
@login_required
def delete_evaluation(evaluation_id):
    """删除评估任务"""
    evaluation = EvaluationService.get_evaluation_by_id(evaluation_id, current_user.id)
    
    if not evaluation:
        flash('评估不存在或您无权访问。', 'error')
        return redirect(url_for('evaluations.evaluations_list'))
    
    try:
        # 删除评估结果
        ModelEvaluationResult.query.filter_by(evaluation_id=evaluation_id).delete()
        
        # 删除评估数据集关联 (ModelEvaluationDataset 记录)
        ModelEvaluationDataset.query.filter_by(evaluation_id=evaluation_id).delete()
        
        # 删除评估记录
        db.session.delete(evaluation)
        db.session.commit()
        
        flash('评估已成功删除。', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"删除评估失败: {str(e)}")
        flash(f'删除评估时发生错误: {str(e)}', 'error')
    
    return redirect(url_for('evaluations.evaluations_list'))

@bp.route('/<int:evaluation_id>/results', methods=['GET'])
@login_required
def view_detailed_results(evaluation_id):
    evaluation = EvaluationService.get_evaluation_by_id(evaluation_id, current_user.id)
    if not evaluation:
        current_app.logger.warning(f"用户 {current_user.id} 尝试访问不存在的评估 {evaluation_id} 的详细结果。")
        abort(404)

    if evaluation.status != 'completed':
        current_app.logger.info(f"用户 {current_user.id} 尝试访问评估 {evaluation_id} 的详细结果，但评估状态为 {evaluation.status}。")
        flash('详细结果仅在评估成功完成后可用。', 'warning')
        return redirect(url_for('evaluations.view_evaluation', evaluation_id=evaluation_id))

    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('search_query', None, type=str)
    min_score = request.args.get('min_score', None, type=float)
    max_score = request.args.get('max_score', None, type=float)
    # 从配置或默认设置每页项目数
    per_page = current_app.config.get('RESULTS_PER_PAGE', 10) 

    results, total_results = EvaluationService.get_evaluation_results(
        evaluation_id=evaluation.id,
        user_id=current_user.id,
        page=page,
        per_page=per_page,
        search_query=search_query,
        min_score=min_score,
        max_score=max_score
    )
    
    if page < 1: # 确保页码至少为1
        page = 1
        
    # 计算总页数，确保即使 total_results 为0时，total_pages 也为0或1（取决于逻辑，这里为0则无分页）
    if total_results > 0:
        total_pages = ceil(total_results / per_page)
    else:
        total_pages = 0 # 或者 1 如果即使没有结果也想显示 "Page 1 of 1"
        
    # 如果请求的页码超出了实际有的页数 (且结果不为空时)，可以重定向到最后一页或第一页
    # 为简单起见，如果请求页码大于总页数且有结果，可以调整为最后一页
    # 但当前分页逻辑在模板中处理，这里仅确保 page >= 1
    # Flask-SQLAlchemy的paginate会自动处理超出范围的页码并返回空列表，所以主要逻辑在模板

    return render_template(
        'evaluations/detailed_results.html',
        evaluation=evaluation,
        results=results,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
        search_query=search_query,
        min_score=min_score,
        max_score=max_score,
        total_results=total_results 
    )

@bp.route('/export/<int:evaluation_id>', methods=['GET'])
@login_required
def export_to_excel(evaluation_id):
    """导出评估结果到Excel"""
    evaluation = EvaluationService.get_evaluation_by_id(evaluation_id, current_user.id)
    
    if not evaluation:
        flash('评估不存在或您无权访问。', 'error')
        return redirect(url_for('evaluations.evaluations_list'))
    
    if evaluation.status != 'completed':
        flash('评估结果仅在评估成功完成后可用。', 'warning')
        return redirect(url_for('evaluations.view_evaluation', evaluation_id=evaluation_id))

    try:
        # 获取筛选参数
        search_query = request.args.get('search_query', None, type=str)
        min_score = request.args.get('min_score', None, type=float)
        max_score = request.args.get('max_score', None, type=float)
        
        # 导出Excel
        excel_data = EvaluationService.export_evaluation_results_to_excel(
            evaluation_id=evaluation_id,
            user_id=current_user.id,
            search_query=search_query,
            min_score=min_score,
            max_score=max_score
        )
        
        if not excel_data:
            flash('没有找到符合条件的评估结果。', 'warning')
            return redirect(url_for('evaluations.view_detailed_results', evaluation_id=evaluation_id))
        
        # 生成文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{evaluation.name}_{timestamp}.xlsx"
        
        # 创建响应
        response = make_response(excel_data)
        response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
        response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        
        return response
        
    except Exception as e:
        current_app.logger.error(f"导出评估结果到Excel失败: {str(e)}")
        flash(f'导出评估结果到Excel时发生错误: {str(e)}', 'error')
        return redirect(url_for('evaluations.view_detailed_results', evaluation_id=evaluation_id)) 
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, current_app
from flask_login import login_required, current_user
from app import db
from app.models import AIModel, SystemDataset, ModelEvaluation, ModelEvaluationResult
from app.services.evaluation_service import EvaluationService

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
        custom_models = AIModel.query.filter_by(user_id=current_user.id, is_system_model=False, is_validated=True).all()
        
        # 获取系统内置模型列表 (裁判模型)
        system_models = AIModel.query.filter_by(is_system_model=True, is_validated=True).all()
        
        # 获取已启用的数据集列表
        datasets = SystemDataset.query.filter_by(is_active=True).order_by(SystemDataset.name).all()
        
        return render_template(
            'evaluations/create_evaluation.html',
            custom_models=custom_models,
            system_models=system_models,
            datasets=datasets,
            title="创建模型评估"
        )
    
    elif request.method == 'POST':
        try:
            # 获取表单数据
            model_id = request.form.get('model_id', type=int)
            judge_model_id = request.form.get('judge_model_id', type=int)
            temperature = request.form.get('temperature', type=float, default=0.7)
            max_tokens = request.form.get('max_tokens', type=int, default=2048)
            evaluation_name = request.form.get('evaluation_name', '')
            
            # 验证模型权限
            target_model = AIModel.query.get(model_id)
            judge_model = AIModel.query.get(judge_model_id)
            
            if not target_model or not judge_model:
                flash('所选模型不存在。', 'error')
                return redirect(url_for('evaluations.create_evaluation'))
            
            # 检查用户对被评估模型的权限 (必须是用户的自定义模型)
            if target_model.is_system_model or target_model.user_id != current_user.id:
                flash('您只能选择自己的自定义模型进行评估。', 'error')
                return redirect(url_for('evaluations.create_evaluation'))
                
            # 检查裁判模型是否为系统模型
            if not judge_model.is_system_model:
                flash('裁判模型必须是系统内置模型。', 'error')
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
                dataset = SystemDataset.query.filter_by(id=ds_id, is_active=True).first()
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
                name=evaluation_name
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
    judge_model = AIModel.query.get(evaluation.judge_model_id)
    
    # 获取评估数据集信息 (不再包含子集和分割)
    datasets_info = []
    for eval_dataset_assoc in evaluation.datasets:
        dataset = SystemDataset.query.get(eval_dataset_assoc.dataset_id)
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
        from app.models import ModelEvaluationDataset # 确保导入
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
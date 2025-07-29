from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, current_app
from flask_login import login_required, current_user
from app import db
from app.models import AIModel, Dataset, RAGEvaluation, RAGEvaluationDataset, RAGEvaluationResult
from app.forms import RAGEvaluationForm
from app.services.rag_evaluation_service import RAGEvaluationService
from datetime import datetime
from sqlalchemy import or_, and_
import threading

bp = Blueprint('rag_eval', __name__, url_prefix='/rag-evaluation')

@bp.route('/')
@login_required
def history():
    """RAG评估历史列表页面"""
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    # 获取用户的RAG评估历史
    evaluations_query = RAGEvaluation.query.filter_by(user_id=current_user.id).order_by(RAGEvaluation.created_at.desc())
    
    # 分页
    evaluations = evaluations_query.paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template(
        'rag_evaluation/history.html',
        evaluations=evaluations,
        title="RAG评估历史"
    )

@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """创建RAG评估页面"""
    form = RAGEvaluationForm()
    
    if request.method == 'GET':
        # 获取用户可用的自定义模型列表
        custom_models = AIModel.query.filter_by(is_system_model=False, user_id=current_user.id).order_by(AIModel.display_name.asc()).all()
        
        # 获取系统内置模型列表 (裁判模型)
        system_models = AIModel.query.filter_by(is_system_model=True).order_by(AIModel.display_name.asc()).all()

        all_models = system_models
        all_models.extend(custom_models)

        # 获取用户可用的数据集列表（只显示RAG格式的数据集）
        if current_user.is_authenticated:
            # 用户可以看到公开数据集和自己的私有数据集
            datasets_query = Dataset.query.filter(
                and_(
                    Dataset.is_active == True,
                    Dataset.format == 'RAG',  # 只显示RAG格式的数据集
                    or_(
                        Dataset.visibility == '公开',
                        and_(
                            Dataset.visibility == '不公开',
                            Dataset.source == current_user.username
                        )
                    )
                )
            ).order_by(Dataset.id.desc())
        else:
            # 未登录用户只能看到公开数据集
            datasets_query = Dataset.query.filter(
                and_(
                    Dataset.is_active == True,
                    Dataset.format == 'RAG',
                    Dataset.visibility == '公开'
                )
            ).order_by(Dataset.id.desc())
        
        datasets = datasets_query.all()
        
        # 设置表单选择项
        form.judge_model_id.choices = [(model.id, model.display_name) for model in all_models]
        form.embedding_model_id.choices = [(model.id, model.display_name) for model in all_models]
        form.dataset_id.choices = [(dataset.id, dataset.name) for dataset in datasets]
        
        return render_template(
            'rag_evaluation/create.html',
            form=form,
            title="创建RAG评估"
        )
    
    # POST请求处理
    if request.method == 'POST':
        try:
            # 手动验证表单数据
            name = request.form.get('name', '').strip()
            judge_model_id = request.form.get('judge_model_id')
            judge_temperature = float(request.form.get('judge_temperature', 0.7))
            judge_max_tokens = int(request.form.get('judge_max_tokens', 2048))
            judge_top_k = int(request.form.get('judge_top_k', 20))
            judge_top_p = float(request.form.get('judge_top_p', 0.8))
            embedding_model_id = request.form.get('embedding_model_id')
            embedding_dimension = int(request.form.get('embedding_dimension', 1536))
            evaluation_metrics = request.form.getlist('evaluation_metrics')
            dataset_id = request.form.get('dataset_id')
            
            # 验证必填字段
            if not judge_model_id:
                flash('请选择裁判模型', 'error')
                raise ValueError('裁判模型未选择')
            
            if not embedding_model_id:
                flash('请选择嵌入模型', 'error')
                raise ValueError('嵌入模型未选择')
                
            if not dataset_id:
                flash('请选择一个数据集', 'error')
                raise ValueError('数据集未选择')
                
            if not evaluation_metrics:
                flash('请至少选择一个评估指标', 'error')
                raise ValueError('评估指标未选择')
            
            # 创建RAG评估记录
            evaluation = RAGEvaluation(
                user_id=current_user.id,
                name=name or f"RAG评估_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                judge_model_id=int(judge_model_id),
                judge_temperature=judge_temperature,
                judge_max_tokens=judge_max_tokens,
                judge_top_k=judge_top_k,
                judge_top_p=judge_top_p,
                embedding_model_id=int(embedding_model_id),
                embedding_dimension=embedding_dimension,
                evaluation_metrics=evaluation_metrics,
                status='pending'
            )
            
            db.session.add(evaluation)
            db.session.flush()  # 获取evaluation.id
            
            # 添加数据集关联
            eval_dataset = RAGEvaluationDataset(
                evaluation_id=evaluation.id,
                dataset_id=int(dataset_id),
                subset='default',
                split='test'
            )
            db.session.add(eval_dataset)
            
            db.session.commit()
            
            # 保存ID，避免在线程中使用数据库对象
            evaluation_id = evaluation.id
            evaluation_name = evaluation.name
            
            # 启动后台评估任务
            app = current_app._get_current_object()  # 获取应用实例
            def run_evaluation():
                with app.app_context():
                    RAGEvaluationService.run_evaluation_async(evaluation_id)
            
            # 在后台线程中运行评估
            eval_thread = threading.Thread(target=run_evaluation)
            eval_thread.daemon = True
            eval_thread.start()
            
            flash(f'RAG评估任务 "{evaluation_name}" 已创建成功，正在后台运行！', 'success')
            return redirect(url_for('rag_eval.history'))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"创建RAG评估失败: {e}")
            flash('创建RAG评估失败，请稍后重试。', 'error')
    
    form.judge_model_id.choices = [(model.id, model.display_name) for model in all_models]
    form.embedding_model_id.choices = [(model.id, model.display_name) for model in all_models]
    form.dataset_id.choices = [(dataset.id, dataset.name) for dataset in datasets]
    
    return render_template(
        'rag_evaluation/create.html',
        form=form,
        title="创建RAG评估"
    )

@bp.route('/<int:evaluation_id>')
@login_required
def detail(evaluation_id):
    """RAG评估详情页面"""
    evaluation = RAGEvaluation.query.filter_by(
        id=evaluation_id,
        user_id=current_user.id
    ).first_or_404()
    
    # 获取评估结果
    results = RAGEvaluationResult.query.filter_by(
        evaluation_id=evaluation_id
    ).order_by(RAGEvaluationResult.id.asc()).all()
    
    return render_template(
        'rag_evaluation/detail.html',
        evaluation=evaluation,
        results=results,
        title=f"RAG评估详情 - {evaluation.name}"
    )

@bp.route('/<int:evaluation_id>/delete', methods=['POST'])
@login_required
def delete(evaluation_id):
    """删除RAG评估"""
    evaluation = RAGEvaluation.query.filter_by(
        id=evaluation_id,
        user_id=current_user.id
    ).first_or_404()
    
    try:
        db.session.delete(evaluation)
        db.session.commit()
        flash(f'RAG评估 "{evaluation.name}" 已删除。', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"删除RAG评估失败: {e}")
        flash('删除RAG评估失败，请稍后重试。', 'error')
    
    return redirect(url_for('rag_eval.history'))

@bp.route('/<int:evaluation_id>/status')
@login_required
def get_status(evaluation_id):
    """获取RAG评估状态（AJAX接口）"""
    evaluation = RAGEvaluation.query.filter_by(
        id=evaluation_id,
        user_id=current_user.id
    ).first_or_404()
    
    return jsonify({
        'status': evaluation.status,
        'completed_at': evaluation.completed_at.isoformat() if evaluation.completed_at else None,
        'result_summary': evaluation.result_summary
    })

@bp.route('/result/<int:result_id>')
@login_required
def get_result_detail(result_id):
    """获取单个评估结果的详细信息（AJAX接口）"""
    result = RAGEvaluationResult.query.join(RAGEvaluation).filter(
        RAGEvaluationResult.id == result_id,
        RAGEvaluation.user_id == current_user.id
    ).first_or_404()
    
    return jsonify({
        'id': result.id,
        'user_input': result.user_input,
        'retrieved_contexts': result.retrieved_contexts,
        'response': result.response,
        'reference_answer': result.reference_answer,
        'relevance_score': result.relevance_score,
        'faithfulness_score': result.faithfulness_score,
        'answer_correctness_score': result.answer_correctness_score,
        'context_precision_score': result.context_precision_score,
        'context_recall_score': result.context_recall_score,
        'feedback': result.feedback
    })
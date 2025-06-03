from typing import List, Dict, Any, Optional, Tuple
from app import db
from app.models import (
    ModelEvaluation, 
    ModelEvaluationDataset, 
    ModelEvaluationResult, 
    AIModel, 
    Dataset, 
)
from flask import current_app
import threading
from app.services.model_service import get_decrypted_api_key
from app.utils import get_beijing_time

from evalscope.run import run_task
from evalscope.constants import JudgeStrategy
import os
import json
import pandas as pd

# 辅助函数，尝试将evalscope的Report对象转换为可序列化的字典
def serialize_evalscope_report(report_obj):
    if hasattr(report_obj, 'to_dict') and callable(report_obj.to_dict):
        return report_obj.to_dict()
    try:
        return vars(report_obj) 
    except TypeError:
        return str(report_obj) 

# 定义evalscope输出结构中review目录的名称
OUTPUTS_STRUCTURE_REVIEWS_DIR = 'reviews'

class EvaluationService:
    """模型评估服务，处理评估相关的业务逻辑"""
    
    @staticmethod
    def create_evaluation(
        user_id: int, 
        model_id: int, 
        judge_model_id: int,
        datasets: List[Dict[str, Any]],
        temperature: float, 
        max_tokens: int,
        name: Optional[str] = None,
        limit: Optional[int] = None  # 新增 limit 参数
    ) -> Optional[ModelEvaluation]:
        """
        创建一个新的模型评估任务
        """
        try:
            if not name:
                model = AIModel.query.get(model_id)
                name = f"{model.display_name if model else '未知模型'}的评估_{get_beijing_time().strftime('%Y%m%d_%H%M%S')}"
            
            evaluation = ModelEvaluation(
                user_id=user_id,
                model_id=model_id,
                judge_model_id=judge_model_id,
                name=name,
                temperature=temperature,
                max_tokens=max_tokens,
                status='pending',
                limit=limit  # 保存 limit 值
            )
            db.session.add(evaluation)
            db.session.flush()
            
            for dataset_info in datasets:
                dataset_id = dataset_info.get('dataset_id')
                eval_dataset = ModelEvaluationDataset(
                    evaluation_id=evaluation.id,
                    dataset_id=dataset_id,
                    subset=None, 
                    split=None   
                )
                db.session.add(eval_dataset)
            
            db.session.commit()
            
            app_context = current_app._get_current_object()
            threading.Thread(
                target=EvaluationService._run_evaluation_task, 
                args=(app_context, evaluation.id,)
            ).start()
            
            return evaluation
        
        except Exception as e:
            current_app.logger.error(f"创建评估任务失败: {str(e)}", exc_info=True)
            db.session.rollback()
            return None
    
    @staticmethod
    def _run_evaluation_task(app, evaluation_id: int) -> None: 
        with app.app_context(): 
            current_app.logger.info(f"[评估任务 {evaluation_id}] 开始执行。")
            evaluation = ModelEvaluation.query.get(evaluation_id)
            if not evaluation:
                current_app.logger.error(f"[评估任务 {evaluation_id}] 无法找到评估记录。")
                return
            
            evaluation.status = 'running'
            db.session.commit()
            current_app.logger.info(f"[评估任务 {evaluation_id}] 状态更新为 'running'。")
            
            model_to_evaluate = AIModel.query.get(evaluation.model_id)
            judge_model_for_evalscope = None if evaluation.judge_model_id is None else AIModel.query.get(evaluation.judge_model_id)

            if not model_to_evaluate:
                evaluation.status = 'failed'
                evaluation.result_summary = {"error": "被评估模型不存在"}
                db.session.commit()
                current_app.logger.error(f"[评估任务 {evaluation_id}] 失败: 被评估模型 ID {evaluation.model_id} 不存在。")
                return
            
            judge_api_url = None
            judge_api_key = None
            judge_model_identifier = None
            if judge_model_for_evalscope:
                judge_api_url = judge_model_for_evalscope.api_base_url
                judge_api_key = get_decrypted_api_key(judge_model_for_evalscope)
                judge_model_identifier = judge_model_for_evalscope.model_identifier

            eval_dataset_associations = ModelEvaluationDataset.query.filter_by(evaluation_id=evaluation_id).all()
            dataset_names_for_evalscope = []
            dataset_args = {}  # 新增：为自建数据集准备的dataset_args

            # 获取所有参与评估的数据集的名称 (这些是传递给evalscope的名称)
            for assoc in eval_dataset_associations:
                dataset = Dataset.query.get(assoc.dataset_id)
                if dataset:
                    if dataset.dataset_type == '系统':
                        # 系统数据集直接使用名称
                        dataset_names_for_evalscope.append(dataset.name) 
                    elif dataset.dataset_type == '自建':
                        # 自建数据集根据格式使用general_mcq或general_qa
                        if dataset.format == 'MCQ':
                            if 'general_mcq' not in dataset_names_for_evalscope:
                                dataset_names_for_evalscope.append('general_mcq')
                            
                            # 获取上传目录的路径
                            dataset_file_path = dataset.download_url
                            dataset_dir = os.path.dirname(dataset_file_path)
                            dataset_name = os.path.splitext(os.path.basename(dataset_file_path))[0]
                            
                            # 确保有general_mcq的dataset_args
                            if 'general_mcq' not in dataset_args:
                                dataset_args['general_mcq'] = {
                                    "local_path": dataset_dir,
                                    "subset_list": [dataset_name],
                                    'filters': {'remove_until': '</think>'} 
                                }
                            else:
                                # 如果已存在，添加到subset_list
                                if dataset_name not in dataset_args['general_mcq']['subset_list']:
                                    dataset_args['general_mcq']['subset_list'].append(dataset_name)
                            
                        elif dataset.format == 'QA':
                            if 'general_qa' not in dataset_names_for_evalscope:
                                dataset_names_for_evalscope.append('general_qa')
                            
                            # 获取上传目录的路径
                            dataset_file_path = dataset.download_url
                            dataset_dir = os.path.dirname(dataset_file_path)
                            dataset_name = os.path.splitext(os.path.basename(dataset_file_path))[0]
                            
                            # 确保有general_qa的dataset_args
                            if 'general_qa' not in dataset_args:
                                dataset_args['general_qa'] = {
                                    "local_path": dataset_dir,
                                    "subset_list": [dataset_name],
                                    'filters': {'remove_until': '</think>'} 
                                }
                            else:
                                # 如果已存在，添加到subset_list
                                if dataset_name not in dataset_args['general_qa']['subset_list']:
                                    dataset_args['general_qa']['subset_list'].append(dataset_name)
                        
                        elif dataset.format == 'CUSTOM':
                            dataset_names_for_evalscope.append(dataset.benchmark_name)
                            # 获取上传目录的路径
                            dataset_file_path = dataset.download_url
                            dataset_dir = os.path.dirname(dataset_file_path)
                            dataset_name = os.path.splitext(os.path.basename(dataset_file_path))[0]
                             # 确保有general_qa的dataset_args
                            if 'general_qa' not in dataset_args:
                                dataset_args[dataset.benchmark_name] = {
                                    "local_path": dataset_dir,
                                    "subset_list": [dataset_name],
                                    'filters': {'remove_until': '</think>'} 
                                }
                            else:
                                if dataset_name not in dataset_args[dataset.benchmark_name]['subset_list']:
                                        dataset_args[dataset.benchmark_name]['subset_list'].append(dataset_name)
                        current_app.logger.info(f"[评估任务 {evaluation_id}] 添加自建数据集 {dataset.name}，格式: {dataset.format}，文件路径: {dataset.download_url}")
                else:
                    current_app.logger.warning(f"[评估任务 {evaluation_id}] 数据集ID {assoc.dataset_id} 无法找到或名称为空，已跳过。")
            
            if not dataset_names_for_evalscope:
                evaluation.status = 'failed'
                evaluation.result_summary = {"error": "没有有效的评估数据集"}
                db.session.commit()
                current_app.logger.error(f"[评估任务 {evaluation_id}] 失败: 没有提供有效的数据集进行评估。")
                return

            evalscope_run_timestamp = get_beijing_time().strftime('%Y%m%d_%H%M%S')
            base_output_dir = os.path.join('.', 'outputs', f'eval_{evaluation_id}_{evalscope_run_timestamp}') 
            try:
                os.makedirs(base_output_dir, exist_ok=True)
            except Exception as e:
                current_app.logger.error(f"[评估任务 {evaluation_id}] 创建evalscope输出目录失败: {base_output_dir}, error: {e}")
                evaluation.status = 'failed'
                evaluation.result_summary = {"error": f"创建输出目录失败: {e}"}
                db.session.commit()
                return

            decrypted_api_key = get_decrypted_api_key(model_to_evaluate)

            # 使用TaskConfig格式创建任务配置
            try:
                from evalscope import TaskConfig
            
                task_cfg_args = {
                    'eval_type': 'service', 
                    'api_url': model_to_evaluate.api_base_url,
                    'model': model_to_evaluate.model_identifier, 
                    'api_key': decrypted_api_key if decrypted_api_key else 'NO_API_KEY',
                    'datasets': dataset_names_for_evalscope, # 传递顶层数据集名称
                    'stream': True, 
                    'timeout': 12000, 
                    'work_dir': base_output_dir,
                    'eval_batch_size': 4
                }
                if judge_model_identifier:
                    task_cfg_args['judge_strategy'] = JudgeStrategy.AUTO
                    task_cfg_args['judge_model_args'] = {
                        'model_id': judge_model_identifier,
                        'api_url': judge_api_url if judge_api_url else '',
                        'api_key': judge_api_key if judge_api_key else '',
                        'generation_config': {
                            # 'stream': True,
                            'timeout': 12000,
                            'temperature': evaluation.temperature
                        }
                    }
                
                # 如果有自建数据集，添加dataset_args参数
                if dataset_args:
                    task_cfg_args['dataset_args'] = dataset_args
                    current_app.logger.info(f"[评估任务 {evaluation_id}] 添加dataset_args: {json.dumps(dataset_args, indent=2)}")
                    
                if evaluation.limit and int(evaluation.limit) > 0:
                    task_cfg_args['limit'] = int(evaluation.limit)

                # 使用TaskConfig创建配置对象
                task_cfg = TaskConfig(**task_cfg_args)
                
                current_app.logger.info(f"[评估任务 {evaluation_id}] Evalscope task_cfg: {task_cfg_args}")
            except ImportError:
                # 如果无法导入TaskConfig，则回退到使用字典
                task_cfg = {
                    'eval_type': 'service', 
                    'api_url': model_to_evaluate.api_base_url,
                    'model': model_to_evaluate.model_identifier, 
                    'api_key': decrypted_api_key if decrypted_api_key else 'NO_API_KEY',
                    'datasets': dataset_names_for_evalscope, # 传递顶层数据集名称
                    'stream': True, 
                    'timeout': 12000, 
                    'work_dir': base_output_dir,
                    'generation_config': {
                        'temperature': evaluation.temperature,
                        'max_tokens': evaluation.max_tokens,
                    },
                    'judge_model_args': { 
                        'model_id': judge_model_identifier if judge_model_identifier else '',
                        'api_url': judge_api_url if judge_api_url else '',
                        'api_key': judge_api_key if judge_api_key else ''
                    }
                }
                
                # 如果有自建数据集，添加dataset_args参数
                if dataset_args:
                    task_cfg['dataset_args'] = dataset_args
                    current_app.logger.info(f"[评估任务 {evaluation_id}] 添加dataset_args: {json.dumps(dataset_args, indent=2)}")
                    
                if evaluation.limit and int(evaluation.limit) > 0:
                    task_cfg['limit'] = int(evaluation.limit)

                current_app.logger.info(f"[评估任务 {evaluation_id}] Evalscope task_cfg: {json.dumps(task_cfg, indent=2)}")

            evalscope_final_report = {}
            detailed_results_to_save = [] # 用于存储 ModelEvaluationResult 对象
            eval_successful = False

            try:
                raw_report_from_evalscope = run_task(task_cfg=task_cfg)
                current_app.logger.info(f"[评估任务 {evaluation_id}] Evalscope run_task completed.")
                eval_successful = True

                if isinstance(raw_report_from_evalscope, dict):
                    for ds_name_key, report_obj in raw_report_from_evalscope.items(): # ds_name_key可能包含子集信息, e.g., "cvalues/positive"
                        evalscope_final_report[ds_name_key] = serialize_evalscope_report(report_obj)
                    current_app.logger.info(f"[评估任务 {evaluation_id}] Evalscope report processed and serialized.")
                else:
                    current_app.logger.error(f"[评估任务 {evaluation_id}] Evalscope run_task did not return a dictionary as expected. Got: {type(raw_report_from_evalscope)}")
                    evalscope_final_report = {"error": "Evalscope did not return a dictionary.", "raw_output": str(raw_report_from_evalscope)}
                    eval_successful = False # 标记evalscope处理报告部分失败

                # 如果Evalscope执行成功并且我们获得了报告字典，尝试解析详细结果
                if eval_successful and isinstance(evalscope_final_report, dict) and not evalscope_final_report.get("error"):
                    current_app.logger.info(f"[评估任务 {evaluation_id}] Attempting to parse detailed review files.")
                    # 确保base_output_dir是绝对路径
                    if not os.path.isabs(base_output_dir):
                        base_output_dir = os.path.abspath(base_output_dir)
                    t_base_output_dir = base_output_dir
                    for k in os.listdir(base_output_dir):
                        t_base_output_dir = os.path.join(base_output_dir, k)
                    
                    # fix: model_to_evaluate.model_identifier可能是deepseek/deepseek-r1-0528-qwen3-8b这种格式，需要做个处理
                    t_model_identifier = model_to_evaluate.model_identifier.split('/')[-1]
                    reviews_base_path = os.path.join(t_base_output_dir, OUTPUTS_STRUCTURE_REVIEWS_DIR, t_model_identifier)
                    if os.path.isdir(reviews_base_path):
                        for review_filename_in_dir in os.listdir(reviews_base_path):
                            review_file_path = os.path.join(reviews_base_path, review_filename_in_dir)
                            
                            if os.path.isfile(review_file_path) and review_filename_in_dir.endswith('.jsonl'):
                                current_app.logger.info(f"[评估任务 {evaluation_id}] Processing review file: {review_file_path}")
                                
                                filename_stem = review_filename_in_dir[:-6] # Remove .jsonl
                                
                                # 根据filename_stem查找对应的dataset
                                corresponding_dataset = None
                                for assoc in eval_dataset_associations:
                                    dataset = Dataset.query.get(assoc.dataset_id)
                                    if dataset:
                                        if dataset.dataset_type == '系统':
                                            # 系统数据集直接比较名称
                                            if dataset.name in filename_stem:
                                                corresponding_dataset = dataset
                                                break
                                        elif dataset.dataset_type == '自建':
                                            # 自建数据集比较文件名（去掉扩展名后的部分）
                                            if dataset.download_url:
                                                dataset_filename = os.path.splitext(os.path.basename(dataset.download_url))[0]
                                                if dataset.benchmark_name+'_'+dataset_filename == filename_stem:
                                                    corresponding_dataset = dataset
                                                    break
                                
                                if not corresponding_dataset:
                                    current_app.logger.warning(f"[评估任务 {evaluation_id}] 无法找到filename_stem '{filename_stem}' 对应的数据集，跳过该文件")
                                    continue

                                try:
                                    origin_df = pd.read_json(review_file_path, lines=True)
                                    for _, item in origin_df.iterrows():
                                        raw_input = item.get('raw_input', '')
                                        raw_pred_answer = ''
                                        choices = item.get('choices', [])
                                        if choices and isinstance(choices, list) and len(choices) > 0:
                                            choice = choices[0]
                                            if isinstance(choice, dict) and 'message' in choice and isinstance(choice['message'], dict):
                                                raw_pred_answer = choice['message'].get('content', '')
                                            elif isinstance(choice, dict) and 'content' in choice:
                                                 raw_pred_answer = choice.get('content', '')
                                        
                                        review_data = {}
                                        if choices and isinstance(choices, list) and len(choices) > 0 and isinstance(choices[0], dict):
                                            review_data = choices[0].get('review', {})

                                        parsed_gold_answer = review_data.get('gold', '')
                                        parsed_pred_answer_for_feedback = review_data.get('pred', '') 
                                        score = review_data.get('result')

                                        # 处理不同格式的result
                                        try:
                                            if score is not None:
                                                if isinstance(score, dict):
                                                    # 处理复合结果格式: {"intent_result": true, "slots_result": {"miss_count": 1, "correct_count": 1, "fail_count": 0}}
                                                    if 'intent_result' in score and 'slots_result' in score:
                                                        intent_result = score.get('intent_result', False)
                                                        slots_result = score.get('slots_result', {})
                                                        
                                                        # 计算slot的F1分数
                                                        correct_count = slots_result.get('correct_count', 0)
                                                        miss_count = slots_result.get('miss_count', 0)
                                                        fail_count = slots_result.get('fail_count', 0)
                                                        
                                                        total_predicted = correct_count + fail_count
                                                        total_actual = correct_count + miss_count
                                                        
                                                        if total_predicted > 0 and total_actual > 0:
                                                            precision = correct_count / total_predicted
                                                            recall = correct_count / total_actual
                                                            if precision + recall > 0:
                                                                slot_f1 = 2 * precision * recall / (precision + recall)
                                                            else:
                                                                slot_f1 = 0.0
                                                        else:
                                                            slot_f1 = 0.0
                                                        
                                                        if correct_count + miss_count + fail_count == 0:
                                                            slot_f1 = 1.0
                                                        
                                                        score = float(intent_result) * 0.5 + 0.5 * slot_f1
                                                        current_app.logger.debug(f"[评估任务 {evaluation_id}] 复合结果计算: intent={intent_result}, slot_f1={slot_f1:.4f}, final_score={score:.4f}")
                                                    else:
                                                        # 其他字典格式，尝试转换为float
                                                        score = float(score)
                                                else:
                                                    # 原有的简单数值格式
                                                    score = float(score)
                                        except (ValueError, TypeError) as e:
                                            current_app.logger.warning(f"[评估任务 {evaluation_id}] Could not parse score '{score}' for an item in {review_file_path}. Error: {str(e)}. Setting to None.")
                                            score = None

                                        result_entry = ModelEvaluationResult(
                                            evaluation_id=evaluation.id,
                                            dataset_id=corresponding_dataset.id,  # 使用corresponding_dataset
                                            question=str(raw_input),
                                            model_answer=str(raw_pred_answer),
                                            reference_answer=str(parsed_gold_answer),
                                            score=score,
                                            feedback=str(parsed_pred_answer_for_feedback) 
                                        )
                                        detailed_results_to_save.append(result_entry)
                                    current_app.logger.info(f"[评估任务 {evaluation_id}] Processed {len(detailed_results_to_save)} items from {review_file_path} (total for this file: {len(origin_df)})")
                                except Exception as df_exc:
                                    current_app.logger.error(f"[评估任务 {evaluation_id}] Error processing review file {review_file_path}: {str(df_exc)}", exc_info=True)
                            else:
                                current_app.logger.debug(f"[评估任务 {evaluation_id}] Skipping non-JSONL file or directory in reviews folder: {review_filename_in_dir}")
                    else:
                        current_app.logger.warning(f"[评估任务 {evaluation_id}] Reviews directory not found: {reviews_base_path}. Skipping detailed results parsing.")
                
                # 保存详细结果到数据库
                if detailed_results_to_save:
                    db.session.bulk_save_objects(detailed_results_to_save)
                    current_app.logger.info(f"[评估任务 {evaluation_id}] Saved {len(detailed_results_to_save)} detailed judge results to database.")

                evaluation.result_summary = evalscope_final_report
                evaluation.status = 'completed' if eval_successful else 'failed' # 如果evalscope执行本身就失败了，则最终状态为failed
                if eval_successful and not evalscope_final_report.get("error"): # 仅当evalscope成功且报告有效时标记完成
                     evaluation.status = 'completed'
                else: # 其他情况都算失败
                    evaluation.status = 'failed'
                    if not evalscope_final_report.get("error") and eval_successful: # evalscope执行完但报告为空或非dict
                         evalscope_final_report["error_detail"] = "Evalscope run task finished but report was invalid or empty."
                    evaluation.result_summary = evalscope_final_report


                evaluation.completed_at = get_beijing_time()
                db.session.commit() # 提交所有更改，包括状态、摘要和详细结果
                current_app.logger.info(f"[评估任务 {evaluation_id}] 评估任务处理完毕，状态: {evaluation.status}。Summary: {json.dumps(evalscope_final_report, indent=2)}")


            except Exception as es_exc:
                current_app.logger.error(f"[评估任务 {evaluation_id}] Error during evalscope execution or result processing: {str(es_exc)}", exc_info=True)
                evaluation.status = 'failed'
                evaluation.result_summary = {"error": f"Evalscope execution/processing failed: {str(es_exc)}"}
                db.session.commit() # 确保即使发生异常也提交状态
            
            finally:
                if os.path.isdir(base_output_dir):
                    try:
                        # shutil.rmtree(base_output_dir)
                        current_app.logger.info(f"[评估任务 {evaluation_id}] Successfully cleaned up evalscope output directory: {base_output_dir}")
                    except Exception as cleanup_exc:
                        current_app.logger.error(f"[评估任务 {evaluation_id}] Failed to clean up evalscope output directory {base_output_dir}: {str(cleanup_exc)}")
                else:
                    current_app.logger.warning(f"[评估任务 {evaluation_id}] Evalscope output directory not found for cleanup: {base_output_dir}")
            current_app.logger.info(f"[评估任务 {evaluation_id}] 执行线程结束。")

    @staticmethod
    def get_evaluation_by_id(evaluation_id: int, user_id: int) -> Optional[ModelEvaluation]:
        evaluation = ModelEvaluation.query.get(evaluation_id)
        if not evaluation or evaluation.user_id != user_id:
            return None
        return evaluation
    
    @staticmethod
    def get_evaluations_for_user(user_id: int, page: int = 1, per_page: int = 10) -> Tuple[List[ModelEvaluation], int]:
        query = ModelEvaluation.query.filter_by(user_id=user_id).order_by(ModelEvaluation.created_at.desc())
        total = query.count()
        evaluations = query.paginate(page=page, per_page=per_page, error_out=False).items
        return evaluations, total
    
    @staticmethod
    def get_evaluation_results(
        evaluation_id: int, 
        user_id: int, 
        page: int = 1, 
        per_page: int = 10,
        search_query: Optional[str] = None,  # 搜索查询参数
        min_score: Optional[float] = None,   # 最小分数筛选
        max_score: Optional[float] = None    # 最大分数筛选
    ) -> Tuple[List[ModelEvaluationResult], int]:
        evaluation = ModelEvaluation.query.get(evaluation_id)
        if not evaluation or evaluation.user_id != user_id:
            return [], 0
        
        query = ModelEvaluationResult.query.filter_by(evaluation_id=evaluation_id)
        
        # 如果提供了搜索查询，则添加模糊搜索条件
        if search_query:
            query = query.filter(ModelEvaluationResult.question.ilike(f"%{search_query}%"))
        
        # 添加分数范围筛选条件
        if min_score is not None:
            query = query.filter(ModelEvaluationResult.score >= min_score)
        if max_score is not None:
            query = query.filter(ModelEvaluationResult.score <= max_score)
            
        query = query.order_by(ModelEvaluationResult.id.asc())
        
        total = query.count()
        results = query.paginate(page=page, per_page=per_page, error_out=False).items
        # 为每个结果添加userPrompt
        for result in results:
            try:
                result.user_prompt = EvaluationService._get_user_prompt_for_result(result)
            except Exception as e:
                current_app.logger.error(f"获取结果 {result.id} 的userPrompt失败: {str(e)}")
                result.user_prompt = "无法获取用户提示"
        
        current_app.logger.info(f"[评估结果查询] EvalID: {evaluation_id}, UserID: {user_id}, Page: {page}, Search: '{search_query}', ScoreRange: [{min_score}, {max_score}], Found: {len(results)}, Total: {total}")
        return results, total

    @staticmethod
    def export_evaluation_results_to_excel(
        evaluation_id: int, 
        user_id: int, 
        search_query: Optional[str] = None,
        min_score: Optional[float] = None,
        max_score: Optional[float] = None
    ) -> Optional[bytes]:
        """
        导出评估结果为Excel文件
        
        Args:
            evaluation_id: 评估ID
            user_id: 用户ID
            search_query: 搜索查询
            min_score: 最小分数
            max_score: 最大分数
            
        Returns:
            bytes: Excel文件的二进制数据，失败返回None
        """
        try:
            # 验证权限
            evaluation = ModelEvaluation.query.get(evaluation_id)
            if not evaluation or evaluation.user_id != user_id:
                return None
            
            # 构建查询
            query = ModelEvaluationResult.query.filter_by(evaluation_id=evaluation_id)
            
            # 应用筛选条件
            if search_query:
                query = query.filter(ModelEvaluationResult.question.ilike(f"%{search_query}%"))
            if min_score is not None:
                query = query.filter(ModelEvaluationResult.score >= min_score)
            if max_score is not None:
                query = query.filter(ModelEvaluationResult.score <= max_score)
                
            query = query.order_by(ModelEvaluationResult.id.asc())
            
            # 获取总数但不加载数据
            total_count = query.count()
            if total_count == 0:
                return None
            
            current_app.logger.info(f"开始导出评估结果，总数: {total_count}")
            
            # 创建Excel文件
            from io import BytesIO
            output = BytesIO()
            
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                # 分批处理数据，避免OOM
                batch_size = 100  # 每批处理1000条记录
                all_data = []
                
                # 使用yield_per进行流式查询
                for batch_start in range(0, total_count, batch_size):
                    current_app.logger.info(f"处理批次: {batch_start}-{min(batch_start + batch_size, total_count)}")
                    
                    # 分页查询当前批次
                    batch_results = query.offset(batch_start).limit(batch_size).all()
                    
                    # 处理当前批次数据
                    for idx, result in enumerate(batch_results, start=batch_start + 1):
                        # 使用统一的user_prompt获取方法
                        try:
                            formatted_question = EvaluationService._get_user_prompt_for_result(result)
                        except Exception as e:
                            current_app.logger.error(f"获取结果 {result.id} 的userPrompt失败: {str(e)}")
                            formatted_question = result.question
                        
                        all_data.append({
                            '序号': idx,
                            '问题': formatted_question,
                            '模型回答': result.model_answer,
                            '参考答案': result.reference_answer or '无',
                            '得分': result.score if result.score is not None else '无评分',
                            '数据集': result.dataset.name if result.dataset else '未知数据集'
                        })
                    
                    # 清理当前批次以释放内存
                    del batch_results
                
                # 创建DataFrame
                df = pd.DataFrame(all_data)
                current_app.logger.info(f"创建DataFrame完成，共 {len(df)} 行")
                
                # 写入Excel
                df.to_excel(writer, sheet_name='评估结果', index=False)
                
                # 获取工作表对象进行格式化
                worksheet = writer.sheets['评估结果']
                
                # 调整列宽
                column_widths = {
                    'A': 8,   # 序号
                    'B': 50,  # 问题
                    'C': 50,  # 模型回答
                    'D': 30,  # 参考答案
                    'E': 10,  # 得分
                    'F': 20   # 数据集
                }
                
                for col, width in column_widths.items():
                    worksheet.column_dimensions[col].width = width
                
                # 设置表头样式
                from openpyxl.styles import Font, PatternFill, Alignment
                header_font = Font(bold=True, color='FFFFFF')
                header_fill = PatternFill(start_color='366092', end_color='366092', fill_type='solid')
                
                for cell in worksheet[1]:
                    cell.font = header_font
                    cell.fill = header_fill
                    cell.alignment = Alignment(horizontal='center', vertical='center')
                
                # 设置数据行样式
                for row in worksheet.iter_rows(min_row=2):
                    for cell in row:
                        cell.alignment = Alignment(vertical='top', wrap_text=True)
                
                # 清理DataFrame以释放内存
                del df
                del all_data
            
            output.seek(0)
            file_data = output.getvalue()
            current_app.logger.info(f"Excel导出完成，文件大小: {len(file_data)} bytes")
            return file_data
            
        except Exception as e:
            current_app.logger.error(f"导出Excel失败: {str(e)}")
            return None 

    @staticmethod
    def _get_user_prompt_for_result(result: 'ModelEvaluationResult') -> str:
        """为单个评估结果获取格式化的userPrompt"""
        try:
            # 解析question字段获取原始输入数据
            import ast
            try:
                raw_input_data = json.loads(result.question)
            except (json.JSONDecodeError, TypeError):
                # 如果JSON解析失败，尝试使用ast.literal_eval
                try:
                    raw_input_data = ast.literal_eval(result.question)
                except (ValueError, SyntaxError):
                    # 如果都失败，直接返回原始问题
                    return result.question
            
            # 首先尝试使用adapter生成完整的prompt
            # 通过result.dataset获取数据集信息，然后使用benchmark_name
            dataset = result.dataset
            if not dataset:
                # 如果没有dataset关系，回退到格式化逻辑
                return EvaluationService._format_prompt_from_raw_data(raw_input_data)
            
            benchmark_name = dataset.benchmark_name
            adapter = EvaluationService._get_adapter_for_dataset(benchmark_name)
            
            if adapter:
                try:
                    # 调用adapter的gen_prompt方法
                    prompt_data = adapter.gen_prompt(raw_input_data, benchmark_name, []) 
                    # 提取prompt字段
                    if isinstance(prompt_data, dict):
                        adapter_prompt = prompt_data.get('data', []) or prompt_data.get('user_prompt', '')
                        if adapter_prompt:
                            # 处理不同类型的adapter_prompt
                            if isinstance(adapter_prompt, list):
                                # 如果是列表，拼接成字符串
                                formatted_prompt = '\n'.join(str(item) for item in adapter_prompt)
                            else:
                                # 如果是字符串，直接使用
                                formatted_prompt = str(adapter_prompt)
                            
                            # 将\n转换为真正的换行符
                            formatted_prompt = formatted_prompt.replace('\\n', '\n')
                            
                            return formatted_prompt
                except Exception as e:
                    current_app.logger.warning(f"使用adapter生成prompt失败: {str(e)}")
            
            # 如果adapter方法失败，使用自定义格式化逻辑
            return EvaluationService._format_prompt_from_raw_data(raw_input_data)
                
        except Exception as e:
            current_app.logger.error(f"解析结果userPrompt时出错: {str(e)}")
            return "解析错误"

    @staticmethod
    def _format_prompt_from_raw_data(raw_input_data: dict) -> str:
        """从原始数据格式化完整的prompt显示"""
        try:
            formatted_parts = []
            
            # 处理历史对话
            history = raw_input_data.get('history') or raw_input_data.get('hisotory', [])
            if history and isinstance(history, list):
                for turn_idx, turn in enumerate(history):
                    if isinstance(turn, dict):
                        if turn.get('user'):
                            formatted_parts.append(f"👤 用户: {turn['user']}")
                        if turn.get('assistant'):
                            formatted_parts.append(f"🤖 助手: {turn['assistant']}")
                    elif isinstance(turn, list) and len(turn) >= 2:
                        # 处理 [user, assistant] 格式
                        formatted_parts.append(f"👤 用户: {turn[0]}")
                        formatted_parts.append(f"🤖 助手: {turn[1]}")
                
                # 如果有历史对话，添加分隔符
                if formatted_parts:
                    formatted_parts.append("─" * 50)
            
            # 处理当前问题 - 尝试多个可能的字段名
            current_question = None
            question_fields = ['question', 'user', 'query', 'prompt', 'input']
            
            for field in question_fields:
                if field in raw_input_data:
                    value = raw_input_data[field]
                    if isinstance(value, str) and value.strip():
                        current_question = value.strip()
                        break
            
            if current_question:
                formatted_parts.append(f"👤 用户: {current_question}")
            
            # 处理选择题选项（如果是MCQ格式）
            if 'A' in raw_input_data or 'choices' in raw_input_data:
                choices_text = EvaluationService._format_choices(raw_input_data)
                if choices_text:
                    formatted_parts.append(choices_text)
            
            # 处理系统提示（如果有）
            if 'system' in raw_input_data and raw_input_data['system']:
                system_prompt = raw_input_data['system']
                formatted_parts.insert(0, f"🔧 系统: {system_prompt}")
                formatted_parts.insert(1, "─" * 50)
            
            if formatted_parts:
                return "\n".join(formatted_parts)
            else:
                # 如果所有字段都为空，返回原始数据的字符串表示
                return str(raw_input_data)
                
        except Exception as e:
            current_app.logger.error(f"格式化prompt时出错: {str(e)}")
            return str(raw_input_data)

    @staticmethod
    def _format_choices(raw_input_data: dict) -> str:
        """格式化选择题选项"""
        try:
            choices_parts = []
            
            # 方式1: 处理 A, B, C, D 格式的选项
            option_keys = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
            found_options = []
            
            for key in option_keys:
                if key in raw_input_data and raw_input_data[key]:
                    found_options.append(f"{key}. {raw_input_data[key]}")
            
            if found_options:
                choices_parts.append("📋 选项:")
                choices_parts.extend(found_options)
            
            # 方式2: 处理 choices 数组格式
            elif 'choices' in raw_input_data:
                choices = raw_input_data['choices']
                if isinstance(choices, list):
                    choices_parts.append("📋 选项:")
                    for idx, choice in enumerate(choices):
                        letter = chr(ord('A') + idx)
                        choices_parts.append(f"{letter}. {choice}")
            
            return "\n".join(choices_parts) if choices_parts else ""
            
        except Exception as e:
            current_app.logger.error(f"格式化选项时出错: {str(e)}")
            return ""

    @staticmethod
    def _get_adapter_for_dataset(dataset_name: str):
        """根据数据集名称获取对应的adapter实例"""
        try:
            # 导入BENCHMARK_MAPPINGS
            from evalscope.benchmarks.benchmark import BENCHMARK_MAPPINGS
            
            # 统一通过BENCHMARK_MAPPINGS获取adapter
            if dataset_name in BENCHMARK_MAPPINGS:
                benchmark_meta = BENCHMARK_MAPPINGS[dataset_name]
                adapter_class = benchmark_meta.data_adapter
                return adapter_class(**benchmark_meta.to_dict())
            return None
            
        except Exception as e:
            current_app.logger.error(f"获取数据集 {dataset_name} 的adapter失败: {str(e)}")
            return None 
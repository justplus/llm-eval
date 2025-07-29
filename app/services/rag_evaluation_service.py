import os
import json
import tempfile
from typing import List, Dict, Any, Optional
from datetime import datetime
from flask import current_app
from app import db
from app.models import RAGEvaluation, RAGEvaluationResult, Dataset, AIModel
from app.utils import get_beijing_time
from app.services import model_service
from app.config import get_outputs_dir
from sqlalchemy.orm import object_session

class RAGEvaluationService:
    """RAG评估服务"""
    
    @staticmethod
    def start_evaluation(evaluation_id: int) -> bool:
        """开始RAG评估任务"""
        try:
            # 创建新的会话以确保数据库连接的可靠性
            from sqlalchemy.orm import sessionmaker
            from app import db
            
            # 创建新的数据库会话
            Session = sessionmaker(bind=db.engine)
            session = Session()
            
            try:
                # 使用新会话查询评估任务
                evaluation = session.query(RAGEvaluation).get(evaluation_id)
                if not evaluation:
                    current_app.logger.error(f"RAG评估任务不存在: {evaluation_id}")
                    return False
                
                # 更新状态为运行中
                evaluation.status = 'running'
                session.commit()
                
                current_app.logger.info(f"开始RAG评估任务: {evaluation.name} (ID: {evaluation_id})")
                
                # 准备评估数据
                testset_data = RAGEvaluationService._prepare_testset_data(evaluation)
                if not testset_data:
                    evaluation.status = 'failed'
                    session.commit()
                    return False
                
                # 执行评估
                results = RAGEvaluationService._run_evaluation(evaluation, testset_data)
                
                if results:
                    # 保存评估结果
                    RAGEvaluationService._save_results(evaluation, results)
                    
                    # 计算汇总结果
                    summary = RAGEvaluationService._calculate_summary(results)
                    evaluation.result_summary = summary
                    evaluation.status = 'completed'
                    evaluation.completed_at = get_beijing_time()
                else:
                    evaluation.status = 'failed'
                
                session.commit()
                current_app.logger.info(f"RAG评估任务完成: {evaluation.name}")
                return True
            
            except Exception as e:
                session.rollback()
                current_app.logger.error(f"RAG评估任务执行失败: {e}")
                try:
                    # 尝试更新任务状态为失败
                    evaluation = session.query(RAGEvaluation).get(evaluation_id)
                    if evaluation:
                        evaluation.status = 'failed'
                        session.commit()
                except:
                    pass
                return False
            finally:
                session.close()
                
        except Exception as e:
            current_app.logger.error(f"RAG评估任务初始化失败: {e}")
            return False
    
    @staticmethod
    def _prepare_testset_data(evaluation: RAGEvaluation) -> Optional[List[Dict]]:
        """准备测试数据集"""
        try:
            testset_data = []
            
            # 获取关联的数据集
            for dataset_rel in evaluation.datasets:
                dataset = dataset_rel.dataset
                current_app.logger.info(f"处理数据集: {dataset.name}")
                
                # 读取数据集文件
                if dataset.download_url and os.path.exists(dataset.download_url):
                    with open(dataset.download_url, 'r', encoding='utf-8') as f:
                        for line_num, line in enumerate(f, 1):
                            try:
                                data = json.loads(line.strip())
                                
                                # 转换为RAGAS格式
                                rag_item = {
                                    "user_input": data.get("user_input", ""),
                                    "retrieved_contexts": data.get("retrieved_contexts", []),
                                    "response": data.get("response", ""),
                                    "reference": data.get("reference", ""),
                                    "dataset_id": dataset.id,
                                    "line_number": line_num
                                }
                                
                                # 验证必要字段
                                if rag_item["user_input"] and rag_item["reference"]:
                                    testset_data.append(rag_item)
                                else:
                                    current_app.logger.warning(f"数据集 {dataset.name} 第 {line_num} 行缺少必要字段")
                                    
                            except json.JSONDecodeError as e:
                                current_app.logger.warning(f"数据集 {dataset.name} 第 {line_num} 行JSON解析失败: {e}")
                                continue
                else:
                    current_app.logger.error(f"数据集文件不存在: {dataset.download_url}")
            
            current_app.logger.info(f"准备了 {len(testset_data)} 条测试数据")
            return testset_data if testset_data else None
            
        except Exception as e:
            current_app.logger.error(f"准备测试数据失败: {e}")
            return None
    
    @staticmethod
    def _run_evaluation(evaluation: RAGEvaluation, testset_data: List[Dict]) -> Optional[List[Dict]]:
        """执行RAG评估"""
        try:
            evalscope_run_timestamp = get_beijing_time().strftime('%Y%m%d_%H%M%S')
            base_output_dir = os.path.join(get_outputs_dir(), f'eval_{evaluation.id}_{evalscope_run_timestamp}') 
            os.makedirs(base_output_dir, exist_ok=True)
            testset_file = f'{base_output_dir}/testset.json'
            with open(testset_file, 'w', encoding='utf-8') as f:
                json.dump(testset_data, f, ensure_ascii=False, indent=2)
            
            try:
                # 构建评估配置
                eval_config = RAGEvaluationService._build_eval_config(evaluation, testset_file, base_output_dir)
                
                # 执行评估
                current_app.logger.info("开始执行RAG评估...")
                results = RAGEvaluationService._execute_ragas_evaluation(eval_config, testset_data, base_output_dir)
                
                return results
                
            finally:
                # 清理临时文件
                if os.path.exists(testset_file):
                    os.unlink(testset_file)
                    
        except Exception as e:
            current_app.logger.error(f"执行RAG评估失败: {e}")
            return None
    
    @staticmethod
    def _build_eval_config(evaluation: RAGEvaluation, testset_file: str, work_dir: str) -> Dict[str, Any]:
        """构建评估配置"""
        # 获取裁判模型信息
        judge_model = evaluation.judge_model
        embedding_model = evaluation.embedding_model
        
        eval_config = {
            "eval_backend": "RAGEval",
            "eval_config": {
                "tool": "RAGAS",
                "eval": {
                    "testset_file": testset_file,
                    "critic_llm": {
                        "model_name": judge_model.model_identifier,
                        "api_base": judge_model.api_base_url,
                        "api_key": model_service.get_decrypted_api_key(judge_model),
                        "temperature": evaluation.judge_temperature,
                        "max_tokens": evaluation.judge_max_tokens,
                        "top_k": evaluation.judge_top_k,
                        "top_p": evaluation.judge_top_p
                    },
                    "embeddings": {
                        "model_name": embedding_model.model_identifier,
                        "api_base": embedding_model.api_base_url,
                        "api_key": model_service.get_decrypted_api_key(embedding_model),
                        "dimensions": evaluation.embedding_dimension
                    },
                    "metrics": evaluation.evaluation_metrics or [
                        "Faithfulness",
                        "AnswerRelevancy", 
                        "ContextPrecision",
                        "AnswerCorrectness",
                        "ContextRecall"
                    ],
                    "language": "chinese"
                }
            },
            "work_dir": work_dir
        }
        
        return eval_config
    
    @staticmethod
    def _execute_ragas_evaluation(eval_config: Dict[str, Any], testset_data: List[Dict], work_dir: str) -> List[Dict]:
        """执行RAGAS评估"""
        try:
            from evalscope.run import run_task
            
            current_app.logger.info("开始执行RAGAS评估...")
            current_app.logger.info(f"评估配置: {eval_config}")
            
            # 使用evalscope运行评估任务
            run_task(task_cfg=eval_config)
            results = []
            # 解析evalscope的结果并转换为我们需要的格式
            eval_results = []
            score_file = f'{work_dir}/testset_score.json'
            with open(score_file, 'r', encoding='utf-8') as f:
                eval_results = json.load(f)

            
            current_app.logger.info(f"解析到 {len(eval_results)} 条评估结果")
            
            # 处理每条评估结果
            for i, eval_result in enumerate(eval_results):
                # 确保eval_result是字典格式
                if not isinstance(eval_result, dict):
                    current_app.logger.warning(f"第 {i+1} 条结果格式异常: {type(eval_result)}")
                    continue
                
                result_item = {
                    "dataset_id": eval_result.get("dataset_id") or (testset_data[i]["dataset_id"] if i < len(testset_data) else None),
                    "user_input": eval_result.get("user_input", ""),
                    "retrieved_contexts": eval_result.get("retrieved_contexts", []),
                    "reference_answer": eval_result.get("reference", ""),
                    "response": eval_result.get("response", ""),
                    "feedback": f"RAGAS评估结果 - 第{i+1}条数据"
                }
                
                # 从evalscope结果中提取各指标分数
                result_item["faithfulness_score"] = eval_result.get("faithfulness")
                result_item["relevance_score"] = eval_result.get("answer_relevancy") 
                result_item["context_precision_score"] = eval_result.get("context_precision")
                result_item["answer_correctness_score"] = eval_result.get("answer_correctness")
                result_item["context_recall_score"] = eval_result.get("context_recall")
                
                results.append(result_item)
            
            current_app.logger.info(f"RAGAS评估完成，生成了 {len(results)} 条结果")
            return results
            
        except ImportError as e:
            current_app.logger.error(f"无法导入evalscope: {e}")
            return []
        except Exception as e:
            current_app.logger.error(f"执行RAGAS评估失败: {e}")
            return []
    
    @staticmethod
    def _save_results(evaluation: RAGEvaluation, results: List[Dict]):
        """保存评估结果"""
        session = object_session(evaluation)  # 获取evaluation关联的会话
        
        try:
            for result in results:
                eval_result = RAGEvaluationResult(
                    evaluation_id=evaluation.id,
                    dataset_id=result["dataset_id"],
                    user_input=result["user_input"],
                    retrieved_contexts=result.get("retrieved_contexts"),
                    reference_answer=result["reference_answer"],
                    relevance_score=result.get("relevance_score"),
                    faithfulness_score=result.get("faithfulness_score"),
                    answer_correctness_score=result.get("answer_correctness_score"),
                    context_precision_score=result.get("context_precision_score"),
                    context_recall_score=result.get("context_recall_score"),
                    feedback=result.get("feedback")
                )
                session.add(eval_result)
            
            # 不在这里提交会话，由调用者负责提交
            current_app.logger.info(f"保存了 {len(results)} 条评估结果")
            
        except Exception as e:
            current_app.logger.error(f"保存评估结果失败: {e}")
            raise
    
    @staticmethod
    def _calculate_summary(results: List[Dict]) -> Dict[str, Any]:
        """计算汇总结果"""
        try:
            summary = {
                "total_count": len(results),
                "completed_at": datetime.now().isoformat()
            }
            
            # 计算各指标的平均分
            metrics = ["relevance_score", "faithfulness_score", "answer_correctness_score", 
                      "context_precision_score", "context_recall_score"]
            
            for metric in metrics:
                scores = [r.get(metric) for r in results if r.get(metric) is not None]
                if scores:
                    summary[f"avg_{metric}"] = round(sum(scores) / len(scores), 3)
                    summary[f"min_{metric}"] = round(min(scores), 3)
                    summary[f"max_{metric}"] = round(max(scores), 3)
            
            return summary
            
        except Exception as e:
            current_app.logger.error(f"计算汇总结果失败: {e}")
            return {"total_count": len(results), "error": str(e)}

    @staticmethod
    def run_evaluation_async(evaluation_id: int):
        """异步运行RAG评估（后台任务）"""
        try:
            # 在新的数据库会话中执行评估，避免使用已关闭的会话
            from sqlalchemy.orm import sessionmaker
            from app import db
            from app.models import RAGEvaluation
            
            # 创建新的数据库会话
            Session = sessionmaker(bind=db.engine)
            session = Session()
            
            try:
                # 检查评估任务是否存在
                evaluation = session.query(RAGEvaluation).get(evaluation_id)
                if not evaluation:
                    current_app.logger.error(f"找不到RAG评估任务: {evaluation_id}")
                    return False
                
                # 执行评估
                result = RAGEvaluationService.start_evaluation(evaluation_id)
                session.commit()
                return result
            except Exception as e:
                session.rollback()
                current_app.logger.error(f"RAG评估执行失败: {e}")
                return False
            finally:
                session.close()
                
        except Exception as e:
            current_app.logger.error(f"异步RAG评估任务失败: {e}")
            return False
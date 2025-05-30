from flask import current_app
from app import db
from app.models import PerformanceEvalTask, AIModel, SystemDataset
from app.utils import get_beijing_time
from datetime import datetime, timezone
import json
import multiprocessing
import tempfile
import os
import traceback
import pickle
import signal
import time
import re
from typing import Tuple, Dict, List, Any, Optional

# evalscope导入
from evalscope.perf.main import run_perf_benchmark

# 导入自定义数据集插件，确保装饰器能够正确注册
from app.adapter.general_intent_dataset_plugin import CustomDatasetPlugin


class PerformanceEvaluationService:
    """性能评估服务类，处理性能评估相关的业务逻辑"""
    
    @staticmethod
    def parse_benchmark_output(output_str: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """
        简易解析 run_perf_benchmark 的输出。
        这部分需要根据实际输出格式进行健壮的解析。
        返回 (summary_dict, percentile_list)
        """
        summary_results = {}
        percentile_results = []
        
        # 这是一个非常基础的解析，实际应用中需要更复杂的逻辑
        # 例如使用正则表达式或者更结构化的日志输出
        lines = output_str.split('\n')
        
        summary_section = False
        percentile_section = False
        
        summary_data = {}
        current_percentiles = []

        # 解析 Benchmarking summary
        try:
            summary_start_index = output_str.index("Benchmarking summary:")
            summary_end_index = output_str.index("Percentile results:")
            summary_text = output_str[summary_start_index:summary_end_index]
            
            summary_lines = [line.strip() for line in summary_text.split('\n') if '|' in line and "Key" not in line and "===" not in line and "---" not in line and len(line.split('|')) > 2]
            for line in summary_lines:
                parts = line.split('|')
                if len(parts) >= 3:
                    key = parts[1].strip()
                    value = parts[2].strip()
                    if key and value:
                        summary_data[key] = value
            summary_results = summary_data
        except ValueError:
            current_app.logger.error("无法解析性能评估的 Benchmarking summary 部分")
            summary_results = {"error": "Could not parse summary section"}

        # 解析 Percentile results
        try:
            percentile_start_index = output_str.index("Percentile results:")
            percentile_text = output_str[percentile_start_index:]
            
            header_line = ""
            percentile_data_lines = []

            lines = percentile_text.split('\n')
            header_found = False
            for i, line in enumerate(lines):
                stripped_line = line.strip()
                if not header_found and "Percentiles" in stripped_line and "TTFT (s)" in stripped_line: # 找到表头行
                    header_line = stripped_line
                    header_found = True
                elif header_found and stripped_line.startswith('|') and "---" not in stripped_line and len(stripped_line.split('|')) > 3:
                    percentile_data_lines.append(stripped_line)
                elif header_found and not stripped_line.startswith('|') and len(percentile_data_lines) > 0: # 表格结束
                    break
            
            if header_line and percentile_data_lines:
                headers = [h.strip() for h in header_line.split('|') if h.strip()]
                for data_line in percentile_data_lines:
                    values = [v.strip() for v in data_line.split('|') if v.strip()]
                    if len(values) == len(headers):
                        percentile_entry = dict(zip(headers, values))
                        current_percentiles.append(percentile_entry)
            percentile_results = current_percentiles
        except ValueError:
            current_app.logger.error("无法解析性能评估的 Percentile results 部分")
            percentile_results = [{"error": "Could not parse percentile section"}]
            
        return summary_results, percentile_results

    @staticmethod
    def validate_model_availability(model_name: str) -> Tuple[bool, str]:
        """
        验证模型是否可用
        
        Args:
            model_name: 模型名称
            
        Returns:
            Tuple[bool, str]: (是否可用, 错误信息)
        """
        try:
            # 基本URL格式检查
            if not model_name or len(model_name.strip()) == 0:
                return False, "模型名称不能为空"
            
            # 如果是URL格式，进行基本检查
            if model_name.startswith('http'):
                if not re.match(r'^https?://[\w\.-]+(?::\d+)?(?:/.*)?$', model_name):
                    return False, "模型URL格式不正确"
            
            return True, ""
            
        except Exception as e:
            return False, f"模型验证失败: {str(e)}"

    @staticmethod
    def run_performance_eval_task_process(task_id: int, task_cfg: Dict[str, Any], output_file_path: str):
        """
        在独立进程中执行性能评估任务，并将结果元组直接保存到输出文件
        
        Args:
            task_id: 评估任务ID (仅用于日志)
            task_cfg: 评估任务配置
            output_file_path: 存储结果的临时文件路径
        """
        def timeout_handler(signum, frame):
            raise TimeoutError("性能评估任务执行超时")
        
        try:
            print(f"开始执行性能评估任务 {task_id}, 配置: {task_cfg}")
            
            # 设置总任务超时时间（15分钟）
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(15 * 60)  # 15分钟超时
            
            start_time = time.time()
            
            # 直接调用run_perf_benchmark获取返回值
            result_tuple = run_perf_benchmark(task_cfg)
            
            # 取消超时信号
            signal.alarm(0)
            
            elapsed_time = time.time() - start_time
            print(f"性能评估任务 {task_id} 执行耗时: {elapsed_time:.2f}秒")
            
            # 将结果序列化到文件
            with open(output_file_path, 'wb') as f:
                pickle.dump(result_tuple, f)
                
            print(f"性能评估任务 {task_id} 已完成，结果已保存到 {output_file_path}")
            
        except TimeoutError:
            signal.alarm(0)
            error_msg = f"性能评估任务 {task_id} 执行超时（15分钟），可能是模型服务不可用"
            print(error_msg)
            with open(output_file_path, 'wb') as f:
                pickle.dump(("ERROR", error_msg), f)
                
        except Exception as e:
            signal.alarm(0)
            error_str = str(e).lower()
            
            # 检查是否是模型服务相关的错误
            if any(keyword in error_str for keyword in ['502', 'bad gateway', 'connection', 'timeout', 'network', 'refused']):
                error_msg = f"模型服务不可用: {str(e)}"
            else:
                error_msg = f"性能评估任务 {task_id} 执行失败: {str(e)}"
                
            print(error_msg)
            print(traceback.format_exc())
            
            # 将错误信息写入输出文件
            with open(output_file_path, 'wb') as f:
                pickle.dump(("ERROR", error_msg), f)

    @staticmethod
    def update_task_from_output_file(app, task_id: int, output_file_path: str):
        """
        从输出文件中读取结果元组并更新任务
        
        Args:
            app: Flask应用实例
            task_id: 评估任务ID
            output_file_path: 结果文件路径
        """
        with app.app_context():
            try:
                # 获取任务
                task = PerformanceEvalTask.query.get(task_id)
                if not task:
                    current_app.logger.error(f"找不到任务ID {task_id}")
                    return
                
                # 更新任务状态为running
                task.status = 'running'
                task.started_at = get_beijing_time()
                db.session.commit()
                
                # 循环检查输出文件是否已完成
                max_wait_time = 15 * 60  # 最长等待时间 (15分钟，与执行超时时间一致)
                start_time = time.time()
                
                while time.time() - start_time < max_wait_time:
                    # 进程是否仍在运行
                    if output_file_path and os.path.exists(output_file_path):
                        # 检查文件是否有内容
                        if os.path.getsize(output_file_path) > 0:
                            # 检查文件是否不再被写入 (1秒内大小不变)
                            file_size = os.path.getsize(output_file_path)
                            time.sleep(1)
                            if file_size == os.path.getsize(output_file_path):
                                # 读取结果
                                try:
                                    with open(output_file_path, 'rb') as f:
                                        result = pickle.load(f)
                                    
                                    # 检查是否有错误
                                    if isinstance(result, tuple) and len(result) == 2 and result[0] == "ERROR":
                                        # 处理错误
                                        task.status = 'failed'
                                        task.error_message = result[1]
                                        task.completed_at = get_beijing_time()
                                        db.session.commit()
                                        current_app.logger.error(f"性能评估任务 {task_id} 失败: {result[1]}")
                                        return
                                    
                                    # 处理正常结果元组
                                    if isinstance(result, tuple) and len(result) == 2:
                                        summary, percentiles = result
                                        
                                        # 移除不需要的字段
                                        if 'Result DB path' in summary:
                                            del summary['Result DB path']
                                        
                                        # 性能评估汇总 - 转换为有序文本
                                        summary_text = PerformanceEvaluationService._convert_summary_to_text(summary)
                                        
                                        # 百分位指标 - 转换为有序文本
                                        percentile_text = PerformanceEvaluationService._convert_percentiles_to_text(percentiles)
                                        
                                        # 格式化原始输出以供查看
                                        raw_output = f"Benchmarking summary:\n"
                                        raw_output += "\n".join([f"{k}: {v}" for k, v in summary.items()]) + "\n\n"
                                        raw_output += "Percentile results:\n"
                                        # 格式化百分位结果
                                        if percentiles and isinstance(percentiles, dict) and 'Percentiles' in percentiles:
                                            headers = list(percentiles.keys())
                                            for i in range(len(percentiles['Percentiles'])):
                                                row = []
                                                for h in headers:
                                                    if i < len(percentiles[h]):
                                                        row.append(f"{h}: {percentiles[h][i]}")
                                                raw_output += ", ".join(row) + "\n"
                                        
                                        # 更新任务结果
                                        task.summary_results = summary_text
                                        task.percentile_results = percentile_text
                                        task.raw_output = raw_output
                                        task.status = 'completed'
                                        task.completed_at = get_beijing_time()
                                        db.session.commit()
                                        
                                        current_app.logger.info(f"性能评估任务 {task_id} 已完成")
                                        return
                                        
                                    else:
                                        # 结果格式不正确
                                        task.status = 'failed'
                                        task.error_message = f"不正确的结果格式: {result}"
                                        task.completed_at = get_beijing_time()
                                        db.session.commit()
                                        return
                                        
                                except Exception as parse_error:
                                    task.status = 'failed'
                                    task.error_message = f"读取结果失败: {str(parse_error)}"
                                    task.completed_at = get_beijing_time()
                                    db.session.commit()
                                    return
                    
                    time.sleep(5)  # 每5秒检查一次
                
                # 如果15分钟后还没有完成，标记为失败
                if not task.status in ['completed', 'failed']:
                    if os.path.exists(output_file_path) and os.path.getsize(output_file_path) == 0:
                        task.status = 'failed'
                        task.error_message = "评估过程异常终止，未生成输出文件"
                        task.completed_at = get_beijing_time()
                        db.session.commit()
                        return
                    
                    # 超时处理
                    task.status = 'failed'
                    task.error_message = "评估任务执行超时 (15分钟)"
                    task.completed_at = get_beijing_time()
                    db.session.commit()
                    
            except Exception as e:
                try:
                    task.status = 'failed'
                    task.error_message = str(e)
                    task.completed_at = get_beijing_time()
                    db.session.commit()
                except Exception as update_error:
                    current_app.logger.error(f"更新任务状态失败: {update_error}")
                    
            finally:
                # 清理临时文件
                if output_file_path and os.path.exists(output_file_path):
                    try:
                        os.remove(output_file_path)
                        current_app.logger.info(f"已清理临时输出文件: {output_file_path}")
                    except Exception as cleanup_error:
                        current_app.logger.warning(f"清理临时文件失败: {cleanup_error}")

    @staticmethod
    def _convert_summary_to_text(summary: Dict[str, Any]) -> str:
        """将汇总数据转换为文本格式"""
        # 定义汇总指标的显示顺序
        summary_order = [
            'Time taken for tests (s)',
            'Number of concurrency',
            'Total requests',
            'Succeed requests',
            'Failed requests',
            'Output token throughput (tok/s)',
            'Total token throughput (tok/s)',
            'Request throughput (req/s)',
            'Average latency (s)',
            'Average time to first token (s)',
            'Average time per output token (s)',
            'Average input tokens per request',
            'Average output tokens per request',
            'Average package latency (s)',
            'Average package per request',
            'Expected number of requests'
        ]
        
        # 按顺序生成汇总文本
        summary_text = ""
        for key in summary_order:
            if key in summary:
                summary_text += f"{key}|{summary[key]}\n"
        
        # 添加未在顺序列表中的其他指标
        for key, value in summary.items():
            if key not in summary_order:
                summary_text += f"{key}|{value}\n"
                
        return summary_text

    @staticmethod
    def _convert_percentiles_to_text(percentiles: Dict[str, List]) -> str:
        """将百分位数据转换为文本格式"""
        # 定义百分位指标的显示顺序
        percentile_order = [
            'Percentile',
            'TTFT (s)',
            'ITL (s)',
            'TPOT (s)',
            'Latency (s)',
            'Input tokens',
            'Output tokens',
            'Output throughput(tok/s)',
            'Total throughput(tok/s)'
        ]
        
        # 按顺序生成百分位文本
        percentile_text = ""
        for key in percentile_order:
            if key in percentiles:
                percentile_text += f"{key}|{','.join(map(str, percentiles[key]))}\n"
        
        # 添加未在顺序列表中的其他指标
        for key, value in percentiles.items():
            if key not in percentile_order:
                percentile_text += f"{key}|{','.join(map(str, value))}\n"
                
        return percentile_text

    @staticmethod
    def create_performance_eval_task(model_id: int, dataset_id: int, concurrency: int, num_requests: int, user_id: int) -> Optional[PerformanceEvalTask]:
        """
        创建性能评估任务
        
        Args:
            model_id: 模型ID
            dataset_id: 数据集ID
            concurrency: 并发数
            num_requests: 请求数量
            user_id: 用户ID
            
        Returns:
            PerformanceEvalTask: 创建的任务对象，失败返回None
        """
        try:
            # 根据ID查询模型和数据集
            model = AIModel.query.get(model_id)
            if not model:
                current_app.logger.error(f"模型ID {model_id} 不存在")
                return None
                
            dataset = SystemDataset.query.get(dataset_id)
            if not dataset:
                current_app.logger.error(f"数据集ID {dataset_id} 不存在")
                return None
            
            # 验证模型可用性（使用模型标识符进行验证）
            is_valid, error_msg = PerformanceEvaluationService.validate_model_availability(model.model_identifier)
            if not is_valid:
                current_app.logger.error(f"模型验证失败: {error_msg}")
                return None
            
            # 创建任务
            task = PerformanceEvalTask(
                user_id=user_id,                    # 设置用户ID
                model_name=model.model_identifier,  # 存储模型标识符
                dataset_name=dataset.name,          # 存储数据集名称
                concurrency=concurrency,
                num_requests=num_requests,
                status='pending',
                created_at=get_beijing_time()
            )
            
            db.session.add(task)
            db.session.commit()
            
            current_app.logger.info(f"创建性能评估任务成功，任务ID: {task.id}")
            return task
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"创建性能评估任务失败: {str(e)}")
            return None

    @staticmethod
    def run_performance_evaluation(task_id: int, model_id: int, dataset_id: int, concurrency: int, num_requests: int):
        """
        运行性能评估任务
        
        Args:
            task_id: 任务ID
        """
        try:
            task = PerformanceEvalTask.query.get(task_id)
            if not task:
                current_app.logger.error(f"任务ID {task_id} 不存在")
                return
            
            # 根据模型标识符查找模型
            selected_model = AIModel.query.get(model_id)
            if not selected_model:
                current_app.logger.error(f"找不到模型ID为 {model_id} 的模型")
                return
                
            # 根据数据集名称查找数据集
            selected_dataset = SystemDataset.query.get(dataset_id)
            if not selected_dataset:
                current_app.logger.error(f"找不到数据集ID为 {dataset_id} 的数据集")
                return

            # 构建evalscope配置
            task_cfg = {
                "url": selected_model.api_base_url.rstrip('/') + '/chat/completions' if not selected_model.api_base_url.endswith('/chat/completions') else selected_model.api_base_url,
                "parallel": concurrency,
                "model": selected_model.model_identifier,
                "number": num_requests,
                "api": 'openai',
                "dataset": 'general_intent',
                "dataset_path": selected_dataset.download_url,  # 使用数据集的下载地址
                "stream": True
            }
            
            # 创建临时文件存储结果
            output_file_path = tempfile.mktemp(suffix=f"_perf_eval_{task_id}.pkl")
            
            # 启动评估进程
            process = multiprocessing.Process(
                target=PerformanceEvaluationService.run_performance_eval_task_process,
                args=(task_id, task_cfg, output_file_path)
            )
            process.start()
            
            # 启动监控线程
            from threading import Thread
            monitor_thread = Thread(
                target=PerformanceEvaluationService.update_task_from_output_file,
                args=(current_app._get_current_object(), task_id, output_file_path)
            )
            monitor_thread.start()
            
            current_app.logger.info(f"性能评估任务 {task_id} 已启动")
            
        except Exception as e:
            current_app.logger.error(f"启动性能评估任务 {task_id} 失败: {str(e)}")
            # 将任务状态设为失败
            try:
                task_to_fail = PerformanceEvalTask.query.get(task_id)
                if task_to_fail:
                    task_to_fail.status = 'failed'
                    task_to_fail.error_message = str(e)
                    task_to_fail.completed_at = get_beijing_time()
                    db.session.commit()
            except Exception as update_error:
                current_app.logger.error(f"更新任务失败状态时出错: {update_error}")

    @staticmethod
    def get_task_by_id(task_id: int, user_id: int = None) -> Optional[PerformanceEvalTask]:
        """
        根据ID获取性能评估任务
        
        Args:
            task_id: 任务ID
            user_id: 用户ID（可选，用于权限验证）
            
        Returns:
            PerformanceEvalTask: 任务对象，不存在或无权限返回None
        """
        query = PerformanceEvalTask.query.filter_by(id=task_id)
        if user_id is not None:
            query = query.filter_by(user_id=user_id)
        return query.first()

    @staticmethod
    def get_all_tasks(user_id: int, page: int = 1, per_page: int = 10) -> Tuple[List[PerformanceEvalTask], int]:
        """
        获取用户的性能评估任务（分页）
        
        Args:
            user_id: 用户ID
            page: 页码
            per_page: 每页数量
            
        Returns:
            Tuple[List[PerformanceEvalTask], int]: (任务列表, 总数)
        """
        query = PerformanceEvalTask.query.filter_by(user_id=user_id).order_by(PerformanceEvalTask.created_at.desc())
        total = query.count()
        tasks = query.paginate(page=page, per_page=per_page, error_out=False).items
        return tasks, total

    @staticmethod
    def delete_task(task_id: int, user_id: int) -> bool:
        """
        删除性能评估任务
        
        Args:
            task_id: 任务ID
            user_id: 用户ID（用于权限验证）
            
        Returns:
            bool: 删除成功返回True，失败返回False
        """
        try:
            task = PerformanceEvalTask.query.filter_by(id=task_id, user_id=user_id).first()
            if not task:
                return False
            
            db.session.delete(task)
            db.session.commit()
            
            current_app.logger.info(f"删除性能评估任务 {task_id} 成功")
            return True
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"删除性能评估任务 {task_id} 失败: {str(e)}")
            return False 
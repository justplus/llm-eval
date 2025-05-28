from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from app import db
from app.models import PerformanceEvalTask, AIModel, SystemDataset
from app.forms import PerformanceEvalForm
from datetime import datetime, timezone
import json # 用于解析和存储结果
import multiprocessing # 使用进程替代线程
import tempfile # 用于创建临时文件
import os # 用于文件操作
import traceback # 用于详细错误信息
import pickle # 用于序列化结果
from sqlalchemy import and_, or_

# evalscope导入
from evalscope.perf.main import run_perf_benchmark

# 导入自定义数据集插件，确保装饰器能够正确注册
from app.adapter.general_intent_dataset_plugin import CustomDatasetPlugin

perf_eval_bp = Blueprint('perf_eval', __name__, url_prefix='/perf_eval')

def parse_benchmark_output(output_str):
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
            if not header_found and "Percentile" in stripped_line and "TTFT (s)" in stripped_line: # 找到表头行
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

def run_performance_eval_task_process(task_id, task_cfg, output_file_path):
    """
    在独立进程中执行性能评估任务，并将结果元组直接保存到输出文件
    
    Args:
        task_id: 评估任务ID (仅用于日志)
        task_cfg: 评估任务配置
        output_file_path: 存储结果的临时文件路径
    """
    try:
        print(f"开始执行性能评估任务 {task_id}, 配置: {task_cfg}")
        
        # 直接调用run_perf_benchmark获取返回值
        result_tuple = run_perf_benchmark(task_cfg)
        
        # 将结果序列化到文件
        with open(output_file_path, 'wb') as f:
            pickle.dump(result_tuple, f)
            
        print(f"性能评估任务 {task_id} 已完成，结果已保存到 {output_file_path}")
        
    except Exception as e:
        print(f"性能评估任务 {task_id} 执行失败: {e}")
        print(traceback.format_exc())
        # 将错误信息写入输出文件
        with open(output_file_path, 'wb') as f:
            pickle.dump(("ERROR", str(e) + "\n" + traceback.format_exc()), f)

def update_task_from_output_file(app, task_id, output_file_path):
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
            task.started_at = datetime.now(timezone.utc)
            db.session.commit()
            
            # 循环检查输出文件是否已完成
            import time
            
            # 最长等待时间 (20分钟)
            max_wait_time = 20 * 60
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
                                    task.completed_at = datetime.now(timezone.utc)
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
                                    
                                    # 百分位指标 - 转换为有序文本
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
                                    
                                    # 格式化原始输出以供查看
                                    raw_output = f"Benchmarking summary:\n"
                                    raw_output += "\n".join([f"{k}: {v}" for k, v in summary.items()]) + "\n\n"
                                    raw_output += "Percentile results:\n"
                                    
                                    # 格式化百分位结果
                                    if percentiles and isinstance(percentiles, dict) and 'Percentile' in percentiles:
                                        headers = list(percentiles.keys())
                                        for i in range(len(percentiles['Percentile'])):
                                            row = []
                                            for h in headers:
                                                if i < len(percentiles[h]):
                                                    row.append(f"{h}: {percentiles[h][i]}")
                                            raw_output += ", ".join(row) + "\n"
                                    
                                    # 更新任务状态和结果
                                    task.summary_results = summary_text
                                    task.percentile_results = percentile_text
                                    task.raw_output = raw_output
                                    task.status = 'completed'
                                    task.completed_at = datetime.now(timezone.utc)
                                    db.session.commit()
                                    
                                    current_app.logger.info(f"性能评估任务 {task_id} 已完成")
                                    return
                                else:
                                    # 结果格式不正确
                                    task.status = 'failed'
                                    task.error_message = f"不正确的结果格式: {result}"
                                    task.completed_at = datetime.now(timezone.utc)
                                    db.session.commit()
                                    return
                            except Exception as parse_error:
                                current_app.logger.error(f"读取性能评估结果失败: {parse_error}")
                                task.status = 'failed'
                                task.error_message = f"读取结果失败: {str(parse_error)}"
                                task.completed_at = datetime.now(timezone.utc)
                                db.session.commit()
                                return
                    
                    # 继续等待
                    time.sleep(5)
                else:
                    # 文件不存在，可能出错了
                    time.sleep(5)
                    if not os.path.exists(output_file_path):
                        task.status = 'failed'
                        task.error_message = "评估过程异常终止，未生成输出文件"
                        task.completed_at = datetime.now(timezone.utc)
                        db.session.commit()
                        return
            
            # 超时
            task.status = 'failed'
            task.error_message = "评估任务执行超时 (20分钟)"
            task.completed_at = datetime.now(timezone.utc)
            db.session.commit()
            
        except Exception as e:
            current_app.logger.error(f"更新任务状态时出错: {e}")
            current_app.logger.error(traceback.format_exc())
            
            # 更新任务状态为失败
            try:
                task = PerformanceEvalTask.query.get(task_id)
                if task:
                    task.status = 'failed'
                    task.error_message = str(e)
                    task.completed_at = datetime.now(timezone.utc)
                    db.session.commit()
            except Exception as update_error:
                current_app.logger.error(f"更新失败任务状态时出错: {update_error}")

@perf_eval_bp.route('/', methods=['GET'])
@login_required
def index():
    """主入口，重定向到创建新评估页面"""
    return redirect(url_for('perf_eval.create'))

@perf_eval_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """创建新的性能评估任务"""
    form = PerformanceEvalForm()
    
    # 动态填充表单选项 - 只选择自建模型，排除系统模型
    available_models = [(m.model_identifier, m.display_name) for m in AIModel.query.filter_by(is_system_model=False).all()]
    
    # 检查是否存在自建模型
    if not available_models:
        flash('您还没有创建任何模型，请先创建模型再进行性能评估。', 'warning')
        # 添加一个空选项，防止表单校验错误
        available_models = [('', '-- 请先创建模型 --')]
    
    # 从数据库中读取所有活跃的自建数据集（只允许自建数据集参与性能评估）
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
    
    # 如果没有可用的自建数据集，添加提示信息
    if not available_datasets:
        flash('没有找到可用的自建数据集，请先创建并启用自建数据集，或等待其他用户公开自建数据集。', 'warning')
        available_datasets = [('', '-- 无可用自建数据集 --')]
    
    form.model_name.choices = available_models
    form.dataset_name.choices = available_datasets

    if form.validate_on_submit():
        # 再次检查模型是否存在（防止用户在没有模型时提交表单）
        if not available_models or available_models[0][0] == '':
            flash('请先创建模型再进行性能评估。', 'error')
            return redirect(url_for('perf_eval.create'))
        
        # 检查数据集是否存在
        if not available_datasets or available_datasets[0][0] == '':
            flash('没有可用的自建数据集，无法进行性能评估。', 'error')
            return redirect(url_for('perf_eval.create'))
            
        try:
            model_identifier = form.model_name.data
            selected_model = AIModel.query.filter_by(model_identifier=model_identifier).first()
            if not selected_model:
                flash('选择的模型未找到!', 'danger')
                return redirect(url_for('perf_eval.create'))

            # 获取选中的数据集信息
            dataset_id = form.dataset_name.data
            selected_dataset = SystemDataset.query.get(dataset_id)
            if not selected_dataset:
                flash('选择的数据集未找到!', 'danger')
                return redirect(url_for('perf_eval.create'))
            
            # 验证数据集是自建类型
            if selected_dataset.dataset_type != '自建':
                flash('只能使用自建数据集进行性能评估!', 'danger')
                return redirect(url_for('perf_eval.create'))
            
            # 验证数据集文件路径存在
            if not selected_dataset.download_url or not os.path.exists(selected_dataset.download_url):
                flash('数据集文件不存在，无法进行性能评估!', 'danger')
                return redirect(url_for('perf_eval.create'))

            task_cfg = {
                "url": selected_model.api_base_url.rstrip('/') + '/chat/completions' if not selected_model.api_base_url.endswith('/chat/completions') else selected_model.api_base_url,
                "parallel": form.concurrency.data,
                "model": model_identifier,
                "number": form.num_requests.data,
                "api": 'openai',
                "dataset": 'general_intent',
                "dataset_path": selected_dataset.download_url,  # 使用实际的文件路径
                "stream": True
            }
            
            current_app.logger.info(f"发起性能评估任务: {task_cfg}")

            # 创建任务记录
            new_task = PerformanceEvalTask(
                model_name=model_identifier,
                dataset_name=selected_dataset.name,
                concurrency=form.concurrency.data,
                num_requests=form.num_requests.data,
                status='pending',  # 初始状态为pending
                created_at=datetime.now(timezone.utc)
                # user_id=current_user.id # 如果需要关联用户
            )
            db.session.add(new_task)
            db.session.commit()
            
            # 创建临时文件存储结果
            output_file = tempfile.NamedTemporaryFile(delete=False, mode='wb', suffix='.pkl')
            output_file_path = output_file.name
            output_file.close()
            
            # 启动后台进程执行评估任务
            process = multiprocessing.Process(
                target=run_performance_eval_task_process,
                args=(new_task.id, task_cfg, output_file_path)
            )
            process.daemon = True  # 使进程成为守护进程
            process.start()
            
            # 启动监控线程检查结果
            import threading
            monitor_thread = threading.Thread(
                target=update_task_from_output_file,
                args=(current_app._get_current_object(), new_task.id, output_file_path)
            )
            monitor_thread.daemon = True
            monitor_thread.start()
            
            # 立即返回，不等待评估完成
            flash('性能评估任务已提交，请稍后查看结果!', 'success')
            return redirect(url_for('perf_eval.results', task_id=new_task.id, source='create'))

        except Exception as e:
            db.session.rollback()
            if 'new_task' in locals() and new_task.id:
                task_to_fail = PerformanceEvalTask.query.get(new_task.id)
                if task_to_fail:
                    task_to_fail.status = 'failed'
                    task_to_fail.error_message = str(e)
                    task_to_fail.completed_at = datetime.now(timezone.utc)
                    db.session.commit()
            current_app.logger.error(f"性能评估失败: {e}", exc_info=True)
            flash(f'性能评估任务发起失败: {e}', 'danger')

    return render_template('perf_eval/create.html', title='发起性能评估', form=form)

@perf_eval_bp.route('/history')
@login_required
def history():
    """查看历史性能评估任务"""
    # 查询历史任务，按创建时间降序排列
    history_tasks = PerformanceEvalTask.query.order_by(PerformanceEvalTask.created_at.desc()).all()
    return render_template('perf_eval/history.html', title='性能评估历史', history_tasks=history_tasks)

@perf_eval_bp.route('/results/<int:task_id>')
@login_required
def results(task_id):
    task = PerformanceEvalTask.query.get_or_404(task_id)
    # 添加一个来源参数，用于区分从创建页面还是历史页面进入
    source = request.args.get('source', 'history')
    
    # 确保 summary_results 和 percentile_results 是Python对象（如果它们是JSON字符串）
    # 在存储时已经转为JSON，取出时 SQLAlchemy 应该会自动转为 Python dict/list
    # 如果不是，可能需要 json.loads()
    return render_template('perf_eval/results.html', title=f'评估结果 - {task.model_name}', task=task, source=source)

@perf_eval_bp.route('/delete/<int:task_id>', methods=['POST'])
@login_required
def delete_task(task_id):
    task = PerformanceEvalTask.query.get_or_404(task_id)
    source = request.args.get('source', 'history')
    # 简单的权限检查，例如： if task.user_id != current_user.id: abort(403)
    try:
        db.session.delete(task)
        db.session.commit()
        flash('评估任务已删除。', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'删除任务失败: {e}', 'danger')
        current_app.logger.error(f"删除性能评估任务失败 {task_id}: {e}")
    
    # 根据来源返回到相应页面
    if source == 'create':
        return redirect(url_for('perf_eval.create'))
    else:
        return redirect(url_for('perf_eval.history'))
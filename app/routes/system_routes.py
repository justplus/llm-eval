"""
系统监控路由
"""
from flask import Blueprint, jsonify, render_template
from flask_login import login_required
from app.utils.thread_utils import get_thread_info, get_system_limits, check_thread_health

bp = Blueprint('system', __name__, url_prefix='/system')

@bp.route('/thread-status')
@login_required
def thread_status():
    """获取线程状态信息"""
    try:
        thread_info = get_thread_info()
        system_limits = get_system_limits()
        is_healthy, health_msg = check_thread_health()
        
        # 获取线程池状态
        thread_pool_status = {}
        try:
            from app.services.evaluation_service import get_evaluation_thread_pool
            from app.routes.rag_eval_routes import get_rag_evaluation_thread_pool
            from app.services.perf_service import get_perf_monitor_thread_pool
            
            eval_pool = get_evaluation_thread_pool()
            rag_pool = get_rag_evaluation_thread_pool()
            perf_pool = get_perf_monitor_thread_pool()
            
            thread_pool_status = {
                'evaluation_pool': {
                    'max_workers': eval_pool._max_workers,
                    'active_threads': len(eval_pool._threads),
                    'pending_tasks': eval_pool._work_queue.qsize()
                },
                'rag_evaluation_pool': {
                    'max_workers': rag_pool._max_workers,
                    'active_threads': len(rag_pool._threads),
                    'pending_tasks': rag_pool._work_queue.qsize()
                },
                'perf_monitor_pool': {
                    'max_workers': perf_pool._max_workers,
                    'active_threads': len(perf_pool._threads),
                    'pending_tasks': perf_pool._work_queue.qsize()
                }
            }
        except Exception as e:
            thread_pool_status = {'error': f'无法获取线程池状态: {e}'}
        
        return jsonify({
            'thread_info': thread_info,
            'system_limits': system_limits,
            'health_status': {
                'is_healthy': is_healthy,
                'message': health_msg
            },
            'thread_pools': thread_pool_status
        })
    except Exception as e:
        return jsonify({'error': f'获取线程状态失败: {e}'}), 500

@bp.route('/health')
def health_check():
    """简单的健康检查端点"""
    try:
        is_healthy, health_msg = check_thread_health()
        return jsonify({
            'status': 'healthy' if is_healthy else 'warning',
            'message': health_msg
        }), 200 if is_healthy else 503
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'健康检查失败: {e}'
        }), 500
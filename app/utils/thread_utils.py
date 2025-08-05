"""
线程管理工具模块
"""
import threading
import resource
import logging
from flask import current_app

def get_thread_info():
    """获取当前线程信息"""
    active_threads = threading.active_count()
    current_thread = threading.current_thread()
    
    return {
        'active_threads': active_threads,
        'current_thread_name': current_thread.name,
        'current_thread_id': current_thread.ident
    }

def get_system_limits():
    """获取系统资源限制"""
    try:
        # 获取进程可创建的最大线程数
        max_threads = resource.getrlimit(resource.RLIMIT_NPROC)[0]
        return {
            'max_threads': max_threads,
            'soft_limit': resource.getrlimit(resource.RLIMIT_NPROC)[0],
            'hard_limit': resource.getrlimit(resource.RLIMIT_NPROC)[1]
        }
    except Exception as e:
        current_app.logger.warning(f"无法获取系统限制: {e}")
        return {
            'max_threads': 'unknown',
            'soft_limit': 'unknown', 
            'hard_limit': 'unknown'
        }

def log_thread_status():
    """记录当前线程状态"""
    thread_info = get_thread_info()
    system_limits = get_system_limits()
    
    current_app.logger.info(f"线程状态 - 活跃线程数: {thread_info['active_threads']}, "
                           f"系统最大线程数: {system_limits['max_threads']}")
    
    # 如果活跃线程数接近系统限制，发出警告
    if (isinstance(system_limits['max_threads'], int) and 
        thread_info['active_threads'] > system_limits['max_threads'] * 0.8):
        current_app.logger.warning(f"警告: 活跃线程数 ({thread_info['active_threads']}) "
                                  f"接近系统限制 ({system_limits['max_threads']})")

def check_thread_health():
    """检查线程健康状态"""
    try:
        thread_info = get_thread_info()
        system_limits = get_system_limits()
        
        # 检查是否有过多的活跃线程
        if isinstance(system_limits['max_threads'], int):
            if thread_info['active_threads'] > system_limits['max_threads'] * 0.9:
                return False, f"线程数过多: {thread_info['active_threads']}/{system_limits['max_threads']}"
        
        return True, "线程状态正常"
    except Exception as e:
        return False, f"检查线程状态时出错: {e}"
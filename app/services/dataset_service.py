import json
import os
import requests
from flask import current_app
from typing import List, Dict, Tuple, Any, Optional
from urllib.parse import quote_plus
import logging

# 导入ModelScope的SDK
from modelscope import MsDataset

class DatasetService:
    """
    提供与ModelScope数据集API交互的服务
    """
    
    @staticmethod
    def get_dataset_structure(dataset_info: Dict) -> Tuple[List[str], Dict[str, List[str]]]:
        """
        从dataset_info中提取子数据集和用途信息
        
        Args:
            dataset_info: 数据集结构信息JSON对象或JSON字符串
            
        Returns:
            Tuple[List[str], Dict[str, List[str]]]: 子数据集列表和每个子数据集对应的用途列表
        """        
        subsets = []
        splits_by_subset = {}
        
        # 如果 dataset_info 是字符串，先解析为字典
        if isinstance(dataset_info, str):
            try:
                dataset_info = json.loads(dataset_info)
            except (json.JSONDecodeError, TypeError) as e:
                # 如果解析失败，返回空结果
                return subsets, splits_by_subset
                
        if dataset_info:
            for subset_name, subset_info in dataset_info.items():
                subsets.append(subset_name)
                if 'splits' in subset_info:
                    splits_by_subset[subset_name] = list(subset_info['splits'].keys())
        
        return subsets, splits_by_subset
    
    @staticmethod
    def get_dataset_data(dataset_info: Dict, subset: str, split: str, dataset_path: str, page: int = 1, per_page: int = 20) -> Tuple[List[Dict], int]:
        """
        获取数据集数据，支持ModelScope API和本地文件读取
        
        Args:
            dataset_info: 数据集结构信息JSON对象
            subset: 子数据集名称
            split: 用途名称
            dataset_path: 数据集路径 (ModelScope数据集名称或本地文件路径)
            page: 页码，从1开始
            per_page: 每页数据条数
            
        Returns:
            Tuple[List[Dict], int]: 数据列表和总数据条数
        """
        if not dataset_path or not subset or not split:
            return [], 0
            
        # 判断是本地文件还是ModelScope数据集
        if os.path.exists(dataset_path):
            # 本地文件处理
            return DatasetService._load_local_dataset(dataset_path, page, per_page)
        else:
            # ModelScope数据集处理
            return DatasetService._load_modelscope_dataset(dataset_path, subset, split, page, per_page)
    
    @staticmethod
    def _load_local_dataset(file_path: str, page: int = 1, per_page: int = 20) -> Tuple[List[Dict], int]:
        """
        加载本地数据集文件 - 优化：流式读取，避免加载整个文件到内存
        
        Args:
            file_path: 本地文件路径
            page: 页码，从1开始
            per_page: 每页数据条数
            
        Returns:
            Tuple[List[Dict], int]: 数据列表和总数据条数
        """
        try:
            file_ext = os.path.splitext(file_path)[1].lower()
            
            if file_ext == '.jsonl':
                # 处理JSONL文件 - 优化：流式读取，不一次性加载所有数据
                return DatasetService._load_jsonl_stream(file_path, page, per_page)
                
            elif file_ext == '.csv':
                # 处理CSV文件 - 优化：流式读取
                return DatasetService._load_csv_stream(file_path, page, per_page)
            else:
                return [], 0
                
        except Exception as e:
            current_app.logger.error(f"Error loading local dataset: {e}")
            return [], 0
    
    @staticmethod
    def _load_jsonl_stream(file_path: str, page: int = 1, per_page: int = 20) -> Tuple[List[Dict], int]:
        """
        流式加载JSONL文件，避免内存占用过高
        """
        try:
            # 快速扫描文件，只计算非空行数（不解析JSON）
            total_valid_lines = 0
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():  # 只检查是否为非空行，不解析JSON
                        total_valid_lines += 1
            
            # 计算分页参数
            start_idx = (page - 1) * per_page
            end_idx = min(start_idx + per_page, total_valid_lines)
            
            # 如果请求的页面超出范围，返回空数据
            if start_idx >= total_valid_lines:
                return [], total_valid_lines
            
            # 第二次扫描，获取目标页的数据
            data = []
            current_valid_line = 0
            
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        # 检查是否在当前页范围内，只有需要的行才解析JSON
                        if start_idx <= current_valid_line < end_idx:
                            try:
                                json_data = json.loads(line)
                                data.append(json_data)
                            except json.JSONDecodeError:
                                # 如果JSON解析失败，创建一个包含原始文本的对象
                                data.append({"error": "JSON解析失败", "raw_text": line[:200] + "..." if len(line) > 200 else line})
                        
                        current_valid_line += 1
                        
                        # 如果已经获取完当前页的数据，提前退出
                        if current_valid_line >= end_idx:
                            break
            
            return data, total_valid_lines
            
        except Exception as e:
            current_app.logger.error(f"Error loading JSONL file: {e}")
            return [], 0
    
    @staticmethod
    def _load_csv_stream(file_path: str, page: int = 1, per_page: int = 20) -> Tuple[List[Dict], int]:
        """
        流式加载CSV文件，避免内存占用过高
        """
        try:
            import csv
            
            # 首先计算总行数（不包括header）
            total_rows = 0
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader, None)  # 跳过header
                for _ in reader:
                    total_rows += 1
            
            # 计算分页参数
            start_idx = (page - 1) * per_page
            end_idx = min(start_idx + per_page, total_rows)
            
            # 如果请求的页面超出范围，返回空数据
            if start_idx >= total_rows:
                return [], total_rows
            
            # 第二次扫描，获取目标页的数据
            data = []
            current_row = 0
            
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    # 检查是否在当前页范围内
                    if start_idx <= current_row < end_idx:
                        data.append(row)
                    
                    current_row += 1
                    
                    # 如果已经获取完当前页的数据，提前退出
                    if current_row >= end_idx:
                        break
            
            return data, total_rows
            
        except Exception as e:
            current_app.logger.error(f"Error loading CSV file: {e}")
            return [], 0
    
    @staticmethod
    def _load_modelscope_dataset(dataset_name: str, subset: str, split: str, page: int = 1, per_page: int = 20) -> Tuple[List[Dict], int]:
        """
        加载ModelScope数据集
        
        Args:
            dataset_name: ModelScope数据集名称
            subset: 子数据集名称
            split: 用途名称
            page: 页码，从1开始
            per_page: 每页数据条数
            
        Returns:
            Tuple[List[Dict], int]: 数据列表和总数据条数
        """
        try:
            # 获取缓存目录，确保在Docker容器中正确工作
            cache_dir = current_app.config.get('DATA_UPLOADS_DIR')
            if not cache_dir:
                # 如果配置中没有设置，使用默认路径
                if os.path.exists('/app') and os.environ.get('FLASK_ENV') == 'production':
                    # Docker容器环境
                    cache_dir = '/app/uploads'
                else:
                    # 非容器环境
                    cache_dir = os.path.join(current_app.root_path, 'uploads')
            
            # 确保缓存目录存在
            os.makedirs(cache_dir, exist_ok=True)
            
            # 加载数据集
            dataset = MsDataset.load(
                dataset_name, 
                subset_name=subset,
                split=split,
                namespace='modelscope',
                cache_dir=cache_dir
            )
            
            # 计算总数据量
            total_items = len(dataset)
            
            # 分页获取数据
            start_idx = (page - 1) * per_page
            end_idx = min(start_idx + per_page, total_items)
            
            # 提取当前页的数据
            data = []
            for i in range(start_idx, end_idx):
                if i < total_items:
                    data.append(dataset[i])
            
            return data, total_items
        except Exception as e:
            current_app.logger.error(f"Error loading data from ModelScope: {e}")
            return [], 0 

    @staticmethod
    def execute_http_request(url: str, method: str = 'GET', headers: Dict = None, data: Any = None) -> str:
        """
        执行HTTP请求，用于jinja2模板中调用
        
        Args:
            url: 请求URL
            method: 请求方法，支持GET/POST
            headers: 请求头，字典格式
            data: POST请求体数据
            
        Returns:
            str: 请求响应内容
        """
        try:
            headers = headers or {}
            method = method.upper()
            
            current_app.logger.info(f"执行HTTP请求: {method} {url}")
            
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=30)
            elif method == 'POST':
                response = requests.post(url, headers=headers, json=data, timeout=30)
            else:
                current_app.logger.error(f"不支持的HTTP方法: {method}")
                return ""
            
            response.raise_for_status()
            return response.text
        except Exception as e:
            current_app.logger.error(f"HTTP请求失败: {e}")
            return ""
    
    @staticmethod
    def create_jinja2_environment(user_input: str = None, context: List[str] = None):
        """
        创建一个jinja2环境，包含HTTP请求功能
        
        Args:
            user_input: 用户输入
            context: 上下文列表
            
        Returns:
            jinja2.Environment: jinja2环境
        """
        from jinja2 import Environment, BaseLoader
        import json
        
        # 创建jinja2环境
        env = Environment(loader=BaseLoader())
        
        # 添加HTTP请求功能
        class HttpRequestWrapper:
            @staticmethod
            def request(url, method='GET', headers=None, data=None):
                return DatasetService.execute_http_request(url, method, headers, data)
                
            @staticmethod
            def urlencode(text):
                if text:
                    return quote_plus(str(text))
                return ""
        
        # 添加全局变量
        env.globals['http'] = HttpRequestWrapper()
        env.globals['user_input'] = user_input
        env.globals['context'] = context
        
        # 添加过滤器
        env.filters['urlencode'] = HttpRequestWrapper.urlencode
        
        # 添加JSON过滤器
        def tojson_filter(value):
            """将Python对象转换为JSON字符串"""
            try:
                return json.dumps(value, ensure_ascii=False)
            except Exception:
                return str(value)
                
        def fromjson_filter(value):
            """将JSON字符串转换为Python对象"""
            try:
                if isinstance(value, str):
                    return json.loads(value)
                return value
            except Exception:
                return value
        
        env.filters['tojson'] = tojson_filter
        env.filters['fromjson'] = fromjson_filter
        
        return env
    
    @staticmethod
    def render_jinja2_template(template_content: str, macro_name: str, **kwargs) -> str:
        """
        渲染jinja2模板中的指定宏
        
        Args:
            template_content: 模板内容
            macro_name: 宏名称
            **kwargs: 传递给宏的参数
            
        Returns:
            str: 渲染结果
        """
        try:
            # 创建jinja2环境
            env = DatasetService.create_jinja2_environment(**kwargs)
            
            # 解析模板
            template = env.from_string(template_content)
            
            # 获取宏
            macro = getattr(template.module, macro_name, None)
            if not macro:
                current_app.logger.error(f"模板中未找到宏: {macro_name}")
                return ""
            
            # 调用宏并返回结果
            return macro(**kwargs)
        except Exception as e:
            current_app.logger.error(f"渲染jinja2模板失败: {e}")
            return None
            
    @staticmethod
    def process_rag_dataset_item(item: Dict, jinja2_template: Optional[str] = None) -> Dict:
        """
        处理RAG数据集项，根据需要使用jinja2模板填充缺失的字段
        
        Args:
            item: RAG数据集项
            jinja2_template: jinja2模板内容
            
        Returns:
            Dict: 处理后的数据集项
        """
        # 如果没有jinja2模板或者已经包含了所需字段，则直接返回
        if not jinja2_template or (item.get('retrieved_contexts') and item.get('response')):
            return item
            
        # 复制一份数据，避免修改原始数据
        processed_item = item.copy()
        user_input = item.get('user_input', '')
        
        # 如果缺少retrieved_contexts字段，使用jinja2模板获取
        if not processed_item.get('retrieved_contexts') and user_input:
            try:
                context_result = DatasetService.render_jinja2_template(
                    jinja2_template, 
                    'get_context', 
                    user_input=user_input
                )
                if not context_result:
                    return None
                
                # 尝试解析结果为JSON列表
                try:
                    contexts = json.loads(context_result)
                    if isinstance(contexts, list):
                        processed_item['retrieved_contexts'] = contexts
                    else:
                        processed_item['retrieved_contexts'] = [context_result]
                except json.JSONDecodeError:
                    # 如果不是JSON格式，则作为单个字符串处理
                    processed_item['retrieved_contexts'] = [context_result] if context_result else []
            except Exception as e:
                current_app.logger.error(f"获取上下文失败: {e}")
                processed_item['retrieved_contexts'] = []
        
        # 如果缺少response字段，使用jinja2模板获取
        if not processed_item.get('response') and user_input:
            try:
                context = processed_item.get('retrieved_contexts', [])
                response_result = DatasetService.render_jinja2_template(
                    jinja2_template, 
                    'get_response', 
                    user_input=user_input,
                    context=context
                )
                if not response_result:
                    return None
                processed_item['response'] = response_result
            except Exception as e:
                current_app.logger.error(f"获取回答失败: {e}")
        
        return processed_item 
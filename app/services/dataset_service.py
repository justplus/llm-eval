import json
import os
from typing import Dict, List, Tuple
from flask import current_app


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
            print(f"Error loading local dataset: {e}")
            return [], 0
    
    @staticmethod
    def _load_jsonl_stream(file_path: str, page: int = 1, per_page: int = 20) -> Tuple[List[Dict], int]:
        """
        流式加载JSONL文件，避免内存占用过高
        """
        try:
            # 首先扫描文件，计算有效行数（非空且JSON有效的行）
            total_valid_lines = 0
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            json.loads(line)
                            total_valid_lines += 1
                        except json.JSONDecodeError:
                            continue
            
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
                        try:
                            json_data = json.loads(line)
                            
                            # 检查是否在当前页范围内
                            if start_idx <= current_valid_line < end_idx:
                                data.append(json_data)
                            
                            current_valid_line += 1
                            
                            # 如果已经获取完当前页的数据，提前退出
                            if current_valid_line >= end_idx:
                                break
                                
                        except json.JSONDecodeError:
                            continue
            
            return data, total_valid_lines
            
        except Exception as e:
            print(f"Error loading JSONL file: {e}")
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
            print(f"Error loading CSV file: {e}")
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
            # 加载数据集
            dataset = MsDataset.load(
                dataset_name, 
                subset_name=subset,
                split=split,
                namespace='modelscope',
                cache_dir=current_app.config.get('DATASET_UPLOAD_FOLDER', os.path.join(current_app.root_path, 'uploads'))
            )
            print(dataset[0])
            
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
            print(f"Error loading data from ModelScope: {e}")
            return [], 0 
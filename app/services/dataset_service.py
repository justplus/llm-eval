import json
import os
from typing import Dict, List, Any, Optional, Tuple

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
            dataset_info: 数据集结构信息JSON对象
            
        Returns:
            Tuple[List[str], Dict[str, List[str]]]: 子数据集列表和每个子数据集对应的用途列表
        """
        subsets = []
        splits_by_subset = {}
        
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
        加载本地数据集文件
        
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
                # 处理JSONL文件 (QA格式和FILL格式)
                data = []
                with open(file_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                data.append(json.loads(line))
                            except json.JSONDecodeError:
                                continue
                
                # 分页处理
                total_items = len(data)
                start_idx = (page - 1) * per_page
                end_idx = min(start_idx + per_page, total_items)
                
                return data[start_idx:end_idx], total_items
                
            elif file_ext == '.csv':
                # 处理CSV文件 (MCQ格式)
                import csv
                data = []
                with open(file_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        data.append(row)
                
                # 分页处理
                total_items = len(data)
                start_idx = (page - 1) * per_page
                end_idx = min(start_idx + per_page, total_items)
                
                return data[start_idx:end_idx], total_items
            else:
                return [], 0
                
        except Exception as e:
            print(f"Error loading local dataset: {e}")
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
                namespace='modelscope'
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
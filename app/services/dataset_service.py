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
    def get_dataset_data(dataset_info: Dict, subset: str, split: str, dataset_name: str, page: int = 1, per_page: int = 20) -> Tuple[List[Dict], int]:
        """
        获取数据集数据，使用ModelScope API读取真实数据
        
        Args:
            dataset_info: 数据集结构信息JSON对象
            subset: 子数据集名称
            split: 用途名称
            dataset_name: 数据集名称 (来自download_url字段)
            page: 页码，从1开始
            per_page: 每页数据条数
            
        Returns:
            Tuple[List[Dict], int]: 数据列表和总数据条数
        """
        # 直接使用ModelScope API获取真实数据
        if not dataset_name or not subset or not split:
            return [], 0
            
        try:
            # 加载数据集
            dataset = MsDataset.load(
                dataset_name, 
                subset_name=subset,
                split=split,
                namespace='modelscope'
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
            print(f"Error loading data from ModelScope: {e}")
            return [], 0 
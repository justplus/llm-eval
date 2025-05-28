from evalscope.benchmarks.benchmark import BENCHMARK_MAPPINGS, BenchmarkMeta  
from evalscope.benchmarks.data_adapter import DataAdapter  
from evalscope.constants import OutputType  
import json
from typing import Dict, Any, List, Union
import os.path
from collections import defaultdict
from evalscope.utils.io_utils import jsonl_to_list
  
# 动态创建DataAdapter类  
class GeneralIntentAdapter(DataAdapter): 
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def load(self, dataset_name_or_path: str = None, subset_list: list = None, **kwargs) -> dict:
        dataset_name_or_path = dataset_name_or_path or self.dataset_id
        subset_list = subset_list or self.subset_list

        data_file_dict = defaultdict(str)
        data_item_dict = defaultdict(list)

        # get data file path and subset name
        if os.path.isdir(dataset_name_or_path):
            for subset_name in subset_list:
                data_file_dict[subset_name] = os.path.join(dataset_name_or_path, f'{subset_name}.jsonl')
        elif os.path.isfile(dataset_name_or_path):
            cur_subset_name = os.path.splitext(os.path.basename(dataset_name_or_path))[0]
            data_file_dict[cur_subset_name] = dataset_name_or_path
        else:
            raise ValueError(f'Invalid dataset path: {dataset_name_or_path}')

        # load data from local disk
        try:
            for subset_name, file_path in data_file_dict.items():
                data_item_dict[subset_name] = jsonl_to_list(file_path)
        except Exception as e:
            raise ValueError(f'Failed to load data from {self.dataset_id}, got error: {e}')

        data_dict = {subset_name: {'test': data_item_dict[subset_name]} for subset_name in data_file_dict.keys()}

        return data_dict

    def gen_prompt(self, input_d: dict, subset_name: str, few_shot_list: list, **kwargs):
        history = input_d.get('history', [])
        system_prompt = input_d.get('system', '')
        user_prompt = input_d.get('question', '') or input_d.get('user', '')
        if history:
            history_prompt = ''
            for h in history:
                for k, v in h.items():
                    history_prompt += f'{k}: {v}\n'
            user_prompt = f"用户的对话内容如下：\n{history_prompt}\nuser: {user_prompt}\n可以使用的工具及其参数为：\n"
        return self.gen_prompt_data(system_prompt=system_prompt, prompt=user_prompt)  
      
    def get_gold_answer(self, input_d: dict) -> str:  
        return input_d.get('answer', '')  
      
    def parse_pred_result(self, result: str, raw_input_d: dict = None, eval_type: str = 'checkpoint') -> str:  
        parsed_result = self._parse_special_format_v2(result.strip())
        if parsed_result:
            return json.dumps(parsed_result, ensure_ascii=False)
        return result.strip()  
      
    def match(self, gold: str, pred: str) -> dict:  
        try:  
            # 尝试解析为JSON  
            gold_data = json.loads(gold)  
            pred_data = json.loads(pred)  
            
            # 如果都是字典，进行intent和slots的详细比较  
            if isinstance(gold_data, dict) and isinstance(pred_data, dict): 
                return self._compare_intent_slots(gold_data, pred_data)  
            else:  
                # 对于其他类型，返回简单的匹配结果
                match_result = 1.0 if gold_data == pred_data else 0.0
                return {"intent_result": match_result == 1.0, "slots_result": {"miss_count": 0, "correct_count": 1 if match_result == 1.0 else 0, "fail_count": 0 if match_result == 1.0 else 1}}
                  
        except (json.JSONDecodeError, TypeError):  
            # 如果不是JSON，回退到字符串比较  
            match_result = 1.0 if gold.strip() == pred.strip() else 0.0
            return {"intent_result": match_result == 1.0, "slots_result": {"miss_count": 0, "correct_count": 1 if match_result == 1.0 else 0, "fail_count": 0 if match_result == 1.0 else 1}} 
    
    def compute_metric(self, review_res_list: Union[List[dict], List[List[dict]]], **kwargs) -> List[dict]:
        intent_correct_count = 0
        all_tp = 0
        all_fp = 0
        all_fn = 0
        for item in review_res_list:
            if item["intent_result"]:
                intent_correct_count += 1
                all_tp += item["slots_result"]["correct_count"]
                all_fp += item["slots_result"]["fail_count"]
                all_fn += item["slots_result"]["miss_count"]

        precision = all_tp / (all_tp + all_fp + 1e-10)
        recall = all_tp / (all_tp + all_fn + 1e-10)
        f1 = 2 * precision * recall / (precision + recall + 1e-10)
        return [
            {'metric_name': 'intent_correct_score', 'score': 0 if len(review_res_list) ==0 else intent_correct_count * 1.0 /len(review_res_list), 'num': len(review_res_list)}, 
            {'metric_name': 'slot_f1', 'score': f1, 'num': all_fn+all_fp+all_tp}
        ]


    def _compare_intent_slots(self, gold_dict: Dict[str, Any], pred_dict: Dict[str, Any]) -> dict:
        """比较intent和slots字段，返回详细的比较结果"""
        result = {
            "intent_result": False,
            "slots_result": {
                "miss_count": 0,    # 预测中缺失的slots
                "correct_count": 0, # 预测正确的slots
                "fail_count": 0     # 预测错误的slots
            }
        }
        # 比较intent字段
        gold_intent = gold_dict.get('intent', '')
        pred_intent = pred_dict.get('intent', '')
        result["intent_result"] = gold_intent == pred_intent
        # 比较slots字段
        gold_slots = gold_dict.get('slots', {})
        pred_slots = pred_dict.get('slots', {})
        
        # 如果gold_slots或pred_slots不是字典，则按字符串比较
        if not isinstance(gold_slots, dict):
            gold_slots = {}
        if not isinstance(pred_slots, dict):
            pred_slots = {}
        
        # 过滤掉value为空字符串的数据
        gold_slots_filtered = {k: v for k, v in gold_slots.items() if v != ''}
        pred_slots_filtered = {k: v for k, v in pred_slots.items() if v != ''}
        
        # 获取所有需要比较的slot键（基于过滤后的数据）
        all_slot_keys = set(gold_slots_filtered.keys())
        
        for slot_key in all_slot_keys:
            gold_value = gold_slots_filtered.get(slot_key, '')
            pred_value = pred_slots_filtered.get(slot_key, '')
            
            if slot_key not in pred_slots_filtered:
                # 预测中缺失的slot
                result["slots_result"]["miss_count"] += 1
            elif str(gold_value) == str(pred_value):
                # 预测正确的slot，有些标注数据类型不对
                result["slots_result"]["correct_count"] += 1
            else:
                # 预测错误的slot
                result["slots_result"]["fail_count"] += 1
        return result
    
    def _parse_special_format_v2(self, text: str) -> dict:
        text = text.strip("```json").strip("```")
        try:
            return json.loads(text)
        except Exception as e:
            return None

    def _parse_special_format(self, text: str) -> dict:
        """解析✿FUNCTION✿和✿ARGS✿格式的文本"""
        try:
            # 初始化结果
            result = {"intent": "", "slots": {}}
            
            # 查找✿FUNCTION✿
            function_start = text.find("✿FUNCTION✿:")
            if function_start != -1:
                # 提取function部分
                function_start += len("✿FUNCTION✿:")
                function_end = text.find("\n", function_start)
                if function_end == -1:
                    function_end = text.find("✿ARGS✿:", function_start)
                if function_end == -1:
                    function_end = len(text)
                
                intent = text[function_start:function_end].strip()
                result["intent"] = intent
            
            # 查找✿ARGS✿
            args_start = text.find("✿ARGS✿:")
            if args_start != -1:
                # 提取args部分
                args_start += len("✿ARGS✿:")
                args_text = text[args_start:].strip()
                
                # 尝试解析JSON
                try:
                    slots = json.loads(args_text)
                    if isinstance(slots, dict):
                        result["slots"] = slots
                    else:
                        # 如果不是字典，将其作为字符串值
                        result["slots"] = {"value": str(slots)}
                except json.JSONDecodeError:
                    # 如果JSON解析失败，将整个args作为字符串
                    result["slots"] = {"raw": args_text}
            
            # 只有当找到了function或args时才返回结果
            if result["intent"] or result["slots"]:
                return result
            
            return None
            
        except Exception as e:
            # 解析失败时返回None，回退到原始文本
            return None

    def _dict_match(self, gold_dict: Dict[str, Any], pred_dict: Dict[str, Any]) -> float:  
        """字典匹配，忽略键的顺序"""  
        if set(gold_dict.keys()) != set(pred_dict.keys()):  
            return 0.0  
          
        for key in gold_dict:  
            if gold_dict[key] != pred_dict[key]:  
                return 0.0  
        return 1.0  
      

# 动态注册基准测试  
def register_genera_intent_benchmark():  
    benchmark_name = f'general_intent'  
      
    # 创建BenchmarkMeta实例  
    benchmark_meta = BenchmarkMeta(  
        name=benchmark_name,  
        dataset_id=benchmark_name,  
        data_adapter=GeneralIntentAdapter,  
        model_adapter=OutputType.GENERATION,  
        subset_list=['default'],  
        metric_list=['AverageAccuracy'],  
        few_shot_num=0,  
        eval_split='test'
    )  
      
    # 直接添加到全局注册表  
    BENCHMARK_MAPPINGS[benchmark_name] = benchmark_meta  
      
    return benchmark_name
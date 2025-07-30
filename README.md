<div align="center">

<h1 align="center">LLM-Eval</h1>

一个强大的大语言模型评估平台，支持多种评估基准、自定义数据集和性能测试。

[功能特性](#功能特性) / [部署教程](#快速开始) / [反馈问题](https://github.com/justplus/llm-eval/issues)


![主界面](./screenshots/100.png)
</div>

## 🔥🔥🔥 更新日志

- 2025/07/29 👋 支持RAG格式的数据集及其基于Ragas的评估
- 2025/06/09 👋 首版本，支持模型PK、效果测评以及性能评估

## 🚀 功能特性

### 🎯 评估能力
- **多基准支持**：内置主流评估基准，支持自定义评估标准
- **智能评分**：基于大模型的自动评分系统，支持多种评分策略
- **数据集管理**：支持QA、MCQ、RAG、自定义格式数据集的上传和管理
- **批量评估**：高效的批量评估处理，支持并发执行

### 📊 性能测试
- **压力测试**：支持并发性能测试，全面评估模型服务性能
- **指标分析**：详细的性能指标统计，包括延迟、吞吐量等关键指标
- **可视化报告**：直观的性能数据展示和分析报告

### 🛠 管理功能
- **模型管理**：统一管理多个LLM模型，支持API配置和密钥管理
- **用户权限**：完善的用户权限控制，支持多用户协作
- **结果导出**：支持评估结果导出为Excel等格式

### 🎨 用户体验
- **现代化UI**：基于DaisyUI的美观界面设计
- **响应式布局**：完美适配桌面端和移动端
- **实时更新**：评估任务状态实时更新，无需手动刷新

### 📸 功能截图

#### 模型管理
![模型管理](./screenshots/101.png)

#### 多模型对话
![多模型对话](./screenshots/102.png)

#### 数据集管理
![数据集管理](./screenshots/103.png)

#### 模型效果评估
![效果评估](./screenshots/104.png)
![评估报告](./screenshots/105.png)
![评估详情](./screenshots/106.png)

#### 模型性能评估
![性能评估](./screenshots/107.png)
![评估报告](./screenshots/108.png)

#### RAG评估
![评估报告](./screenshots/109.png)

## 🏃‍♂️ 快速开始

### 环境要求

- Python 3.10+
- MySQL 5.7+

### 本地开发

```bash
# 克隆项目
git clone https://github.com/your-repo/llm-eva.git
cd llm-eva

# 安装依赖 [evalscope依赖较多耐心等待]
pip install -r requirements.txt

# 配置环境变量
cp .flaskenv.example .flaskenv
# 编辑 .flaskenv 文件，填入数据库配置等信息

# 启动应用
python run.py --port 5000
```

访问 `http://localhost:5000` 开始使用。

### Docker部署

```bash
# 使用 Docker Compose 快速部署
cp .env.example .env
# 编辑 .env 文件，填入数据库配置等信息
docker-compose up -d
```

## 📚 使用指南

### 添加模型

1. 进入"模型管理"页面
2. 点击"添加模型"
3. 填入模型名称、API地址、密钥等信息
4. 保存配置

### 上传数据集

1. 进入"数据集管理"页面
2. 选择数据集格式（QA/MCQ/RAG/自定义）
3. 上传JSON格式的数据文件
4. 配置基准类型和相关参数

### 创建评估任务

1. 进入"评估管理"页面
2. 选择要评估的模型和数据集
3. 配置评估参数（温度、最大Token等）
4. 选择数据集(不包括RAG数据集)
5. 启动评估任务

### 性能评估

1. 进入"性能评估"页面
2. 选择目标模型和测试数据集
3. 设置并发数和请求数量
4. 选择数据集(不包括RAG数据集)
5. 查看性能测试报告

### RAG评估

1. 进入"RAG评估"页面
2. 选择裁判模型和向量嵌入模型
3. 设置评估参数（温度、最大Token等）
4. 选择数据集(仅RAG数据集)
5. 查看RAG评估报告

## 🔍 支持的数据格式

### QA格式
```json
{
  "system": "你是一个有用的助手",
  "query": "什么是机器学习？",
  "response": "机器学习是人工智能的一个分支..."
}
```

### MCQ格式
```json
{
  "question": "以下哪个是机器学习算法？",
  "A": "线性回归",
  "B": "数据清洗", 
  "C": "数据可视化",
  "D": "数据存储",
  "answer": "A"
}
```

### RAG格式
```json
{
    "user_input": "第一届奥运会是什么时候举行的？",
    "retrieved_contexts": [
        "第一届现代奥运会于1896年4月6日到4月15日在希腊雅典举行。",
        "这届奥运会共有来自14个国家的241名运动员参加。"
    ],
    "response": "第一届现代奥运会于1896年4月6日举行。",
    "reference": "第一届现代奥运会于1896年4月6日在希腊雅典开幕。"
}
```
或者
```json
{
    "user_input": "什么是人工智能？",
    "reference": "人工智能是计算机科学的一个分支..."
}
```
注：这种方式需要配合jinja2模板获取retrieved_contexts和response，参考下面的例子

### 自定义格式
```json
{
  "history": [
    {"user": "你好", "assistant": "你好！有什么可以帮助你的吗？"}
  ],
  "question": "请介绍一下你自己",
  "answer": "我是一个AI助手，可以帮助回答问题..."
}
```

## 🛠 开发

### 本地开发环境

```bash
# 安装开发依赖
pip install -r requirements.txt

# 启动开发服务器
python run.py --debug
```

### 自定义数据集
如果你的数据集不是[选择题](#qa格式)、[问答题](#mcq格式)，你可能需要自定义数据集来满足自己的需求。
自定义数据集使用Jinja2模版来实现数据字段和指标的定义。模板需要包含宏：gen_prompt, get_gold_answer, match, parse_pred_result,get_config
其中`get_config`中可配置字段如下：
- llm_as_a_judge: 该数据集是否使用LLM作为裁判，如果使用需要配置裁判模型
- judge_system_prompt: 如果使用裁判模型，裁判模型进行评估时的系统prompt，非必须
- judge_prompt: 如果使用裁判模型，裁判模型进行评估时的prompt，必须。占位符包括：question、system_prompt、hisotry、gold、pred
- metric_list: 度量指标列表，如果提供，需要在match/llm_match子集或系统提供的子集['AverageAccuracy', 'WeightedAverageAccuracy', 'AverageBLEU', 'AverageRouge', 'WeightedAverageBLEU', 'AveragePass@1', 'Pass@1', 'Pass@2', 'Pass@3', 'Pass@4', 'Pass@5', 'Pass@6', 'Pass@7', 'Pass@8', 'Pass@9', 'Pass@10', 'Pass@11', 'Pass@12', 'Pass@13', 'Pass@14', 'Pass@15', 'Pass@16', 'VQAScore', 'PickScore', 'CLIPScore', 'BLIPv2Score', 'HPSv2Score', 'HPSv2.1Score', 'ImageRewardScore', 'FGA_BLIP2Score', 'MPS']中，如果不提供默认是AverageAccuracy


例子1：落域抽槽(不使用裁判模型)：
```jinja2
{# 意图识别评估模板 #}
{# 1. 配置 #}
{% macro get_config() %}
{
    "llm_as_a_judge": false  {# 是否使用LLM作为裁判 #}
}
{% endmacro %}

{# 2. 生成提示词 #}
{% macro gen_prompt(system_prompt, history, user_prompt) %}
{% set final_user_prompt = user_prompt %}
{% if history %}
    {% set history_prompt = '' %}
    {% for h in history %}
        {% for k, v in h.items() %}
            {% set history_prompt = history_prompt ~ k ~ ': ' ~ v ~ '\n' %}
        {% endfor %}
    {% endfor %}
    {% set final_user_prompt = "用户的对话内容如下：\n" ~ history_prompt ~ "user: " ~ user_prompt ~ "\n可以使用的工具及其参数为：\n" %}
{% endif %}
{
    "system_prompt": {{ system_prompt | to_json }},
    "user_prompt": {{ final_user_prompt | to_json }}
}
{% endmacro %}

{# 3. 获取标准答案 #}
{% macro get_gold_answer(input_d) %}
{{ input_d.get('answer', '') }}
{% endmacro %}

{# 4. 解析预测结果 #}
{% macro parse_pred_result(result) %}
{% set text = result.strip() %}
{% set text = text.strip("```json").strip("```") %}

{% set parsed = none %}
{% if text is string %}
    {% set parsed = text | from_json %}
{% endif %}

{% if parsed is not none %}
    {{ parsed | to_json }}
{% else %}
    {{ text }}
{% endif %}
{% endmacro %}

{# 5. 比较预测结果和标准答案 #}
{% macro match(gold, pred) %}
{# 调试日志：输入参数 #}

{% set gold_data = gold | from_json %}
{% set pred_data = pred | from_json %}

{% if gold_data is mapping and pred_data is mapping %}
    {# 比较意图 #}
    {% set intent_match = gold_data.get('intent', '') == pred_data.get('intent', '') %}
    
    {# 比较槽位 #}
    {% set gold_slots = gold_data.get('slots', {}) %}
    {% set pred_slots = pred_data.get('slots', {}) %}

    {# 使用列表来记录各种情况 #}
    {% set miss_slots = [] %}
    {% set correct_slots = [] %}
    {% set fail_slots = [] %}
    
    {# 遍历参考答案中的槽位 #}
    {% for key, value in gold_slots.items() %}
        {% if value != '' %}
            {% if key not in pred_slots %}
                {% set _ = miss_slots.append(key) %}
            {% elif pred_slots[key] == value %}
                {% set _ = correct_slots.append(key) %}
            {% else %}
                {% set _ = fail_slots.append(key) %}
            {% endif %}
        {% endif %}
    {% endfor %}

    
    {# 计算最终结果 #}
    {% set miss_count = miss_slots | length %}
    {% set correct_count = correct_slots | length %}
    {% set fail_count = fail_slots | length %}
    
    {
        "intent_result": {{ intent_match | to_json }},
        "slots_result": {
            "miss_count": {{ miss_count }},
            "correct_count": {{ correct_count }},
            "fail_count": {{ fail_count }}
        }
    }
{% else %}
    {
        "intent_result": {{ (gold == pred) | to_json }},
        "slots_result": {
            "miss_count": 0,
            "correct_count": {{ 1 if gold == pred else 0 }},
            "fail_count": {{ 0 if gold == pred else 1 }}
        }
    }
{% endif %}
{% endmacro %}

{# 6. 计算评估指标 #}
{% macro compute_metric(review_res_list) %}
{# 使用列表来记录各种情况 #}
{% set intent_correct_list = [] %}
{% set tp_list = [] %}
{% set fp_list = [] %}
{% set fn_list = [] %}

{% for item in review_res_list %}
    {% if item.intent_result %}
        {% set _ = intent_correct_list.append(1) %}
        {% set _ = tp_list.append(item.slots_result.correct_count) %}
        {% set _ = fp_list.append(item.slots_result.fail_count) %}
        {% set _ = fn_list.append(item.slots_result.miss_count) %}
    {% endif %}
{% endfor %}

{% set intent_correct_count = intent_correct_list | sum %}
{% set all_tp = tp_list | sum %}
{% set all_fp = fp_list | sum %}
{% set all_fn = fn_list | sum %}

{% set precision = all_tp / (all_tp + all_fp + 1e-10) %}
{% set recall = all_tp / (all_tp + all_fn + 1e-10) %}
{% set f1 = 2 * precision * recall / (precision + recall + 1e-10) %}

[
    {
        "metric_name": "intent_correct_score",
        "score": {{ 0 if review_res_list|length == 0 else intent_correct_count * 1.0 / review_res_list|length }},
        "num": {{ review_res_list|length }}
    },
    {
        "metric_name": "slot_f1",
        "score": {{ f1 }},
        "num": {{ all_fn + all_fp + all_tp }}
    }
]
{% endmacro %}
```

例子2：simpleQA(有参考答案，裁判模型依据参考答案判断)

```jinja2
{# simpleQA评估模板 #}
{# 1. 配置 #}
{% macro get_config() %}
{
    "llm_as_a_judge": true,  {# 是否使用LLM作为裁判 #}
    "judge_system_prompt": "你是一个智能助手，请根据给定问题、标准答案和模型预测的答案来评估模型的回答是否正确。",  {# 裁判系统提示词 #}
    "judge_prompt": "请根据给定问题、标准答案和模型预测的答案来评估模型的回答是否正确。您的任务是将结果评定为：【正确】、【错误】或【未尝试】。\n\n首先，我们将列出每个评定类别的示例，然后请您对新问题的预测答案进行评定。\n以下是【正确】的答复示例：\n```\n问题：贝拉克·奥巴马的孩子叫什么名字？\n标准答案：玛丽亚·奥巴马和萨莎·奥巴马\n模型预测1：Malia Obama and Sasha Obama\n模型预测2：玛丽亚和萨沙\n模型预测3：大多数人会说是玛丽亚和萨莎，但我不确定，需要再确认\n模型预测4：巴拉克·奥巴马有两个女儿，她们分别是玛丽亚·安和娜塔莎·玛丽安，但通常称作玛丽亚·奥巴马和萨莎·奥巴马。玛丽亚出生于1998年7月4日，萨莎出生于2001年6月10日。\n```\n这些答复均为【正确】，因为：\n    - 完整地包含了标准答案中的重要信息。\n    - 不包含任何与标准答案矛盾的信息。\n    - 只关注语义内容，中英文，大小写、标点、语法和顺序不重要。\n    - 答复中出现模糊语句或猜测是可以接受的，前提是包含了标准答案且不含有不正确信息或矛盾。\n\n以下是【错误】的答复示例：\n```\n问题：巴拉克·奥巴马的孩子叫什么名字？\n标准答案：玛丽亚·奥巴马和萨莎·奥巴马\n模型预测1：玛丽亚\n模型预测2：玛丽亚、萨莎和苏珊\n模型预测3：巴拉克·奥巴马没有孩子\n模型预测4：我认为是玛丽亚和萨莎。或者是玛丽亚和杰基。或者是乔伊和玛丽亚。\n模型预测5：虽然我不知道他们的确切名字，但能说出巴拉克·奥巴马有三个孩子。\n模型预测6：你可能是想说贝茜和奥利维亚。不过您应通过最新的参考资料确认详细信息。那是正确的答案吗？\n```\n这些答复均为【错误】，因为：\n    - 答复中包含与标准答案矛盾的事实陈述。即使在陈述中略带保留（例如：'可能是'，'虽然我不确定，但我认为'），也视为错误。\n\n以下是【未尝试】的答复示例：\n```\n问题：巴拉克·奥巴马的孩子叫什么名字？\n标准答案：玛丽亚·奥巴马和萨莎·奥巴马\n模型预测1：我不知道。\n模型预测2：我需要更多关于您所指奥巴马的上下文。\n模型预测3：不查阅网络我无法回答这个问题，不过我知道巴拉克·奥巴马有两个孩子。\n模型预测4：巴拉克·奥巴马有两个孩子。我知道其中一个叫玛丽亚，但我不确定另一个的名字。\n```\n这些答复均为【未尝试】，因为：\n    - 没有包含标准答案中的重要信息。\n    - 回复中没有与标准答案矛盾的陈述。\n\n另外注意以下几点：\n- 对于标准答案为数字的问题，预测答案应和标准答案一致。例如，考虑问题'金山铁路黄浦江特大桥的全长是多少米？'，标准答案为'3518.17'：\n    - 预测答案'3518'、'3518.1'、'3518.17'均为【正确】。\n    - 预测答案'3520'和'3600'均为【错误】。\n    - 预测答案'大约3500米'和'超过3000米'被视为【未尝试】，因为它们既不确认也不与标准答案矛盾。\n- 如果标准答案包含比问题更多的信息，预测答案只需包含问题中提到的信息。\n    - 例如，考虑问题'菱镁矿的主要化学成分是什么？'标准答案为'碳酸镁（MgCO3）'。'碳酸镁'或'MgCO3'均视为【正确】答案。\n- 如果从问题中明显可以推断出预测答案省略的信息，那么算作正确。\n    - 例如，问题'巴鲁米尼的努拉吉遗迹在1997年被联合国教科文组织列为世界文化遗产，那么这遗址在哪个地区？'标准答案为'意大利撒丁岛'，预测答案'撒丁岛'被视为【正确】。\n- 如果能明显看出名字翻译版本不同但是是同一个人也认为正确。\n    - 例如，如果标准答案是'Robinson'，那么回答鲁滨逊或者鲁滨孙均正确。\n\n下面是一个新的问题示例。请只回复A、B、C之一，不要道歉或纠正自己的错误，只需要评估该回答。\n```\n问题: {question}\n正确答案: {gold}\n预测答案: {pred}\n```\n\n将此新问题的预测答案评定为以下之一：\nA:【正确】\nB:【错误】\nC:【未尝试】\n\n只返回字母'A'、'B'或'C'，无须添加其他文本。",  {# 裁判提示词 #}
    "metric_list": ["is_correct", "is_incorrect", "is_not_attempted"] {# 度量指标 #}
}
{% endmacro %}

{# 2. 生成提示词 #}
{% macro gen_prompt(system_prompt, history, user_prompt) %}
{% set final_user_prompt = user_prompt %}
{% if history %}
    {% set history_prompt = '' %}
    {% for h in history %}
        {% for k, v in h.items() %}
            {% set history_prompt = history_prompt ~ k ~ ': ' ~ v ~ '\n' %}
        {% endfor %}
    {% endfor %}
    {% set final_user_prompt = "用户的对话内容如下：\n" ~ history_prompt ~ "user: " ~ user_prompt ~ "\n可以使用的工具及其参数为：\n" %}
{% endif %}
{
    "system_prompt": {{ system_prompt | to_json }},
    "user_prompt": {{ final_user_prompt | to_json }}
}
{% endmacro %}

{# 3. 获取标准答案 #}
{% macro get_gold_answer(input_d) %}
{{ input_d.get('answer', '') }}
{% endmacro %}

{# 4. 解析预测结果 #}
{% macro parse_pred_result(result) %}
{{result | trim}}
{% endmacro %}

{# 5. 比较预测结果和标准答案 #}
{% macro match(gold, pred) %}
{% set is_correct = 1 if gold.lower().strip() == pred.lower().strip() else 0 %}
{% set is_incorrect = 1 if not is_correct else 0 %}
{% set is_not_attempted = 0 %}
{
    "is_correct": {{ is_correct }},
    "is_incorrect": {{ is_incorrect }},
    "is_not_attempted": {{ is_not_attempted }}
}
{% endmacro %}

{# 6. LLM裁判响应解析，llm_as_a_judge会使用到 #}
{% macro llm_match(judge_response) %}
{% set match_result = judge_response | regex_search('(A|B|C)') %}
{% set res = match_result if match_result else 'C' %}
{
    "is_correct": {{ 1 if res == 'A' else 0 }},
    "is_incorrect": {{ 1 if res == 'B' else 0 }},
    "is_not_attempted": {{ 1 if res == 'C' else 0 }},
    "judge_response": {{ judge_response | to_json }}
}
{% endmacro %}

{# 7. 计算评估指标 #}
{# 可以为空，为空时计算伤处指标在数据子集的均值#}
```

例子3：没有参考答案的情况(使用裁判模型直接判断生成结果)：

```jinja2
{# 没有参考答案评估模板 #}
{# 1. 配置 #}
{% macro get_config() %}
{
    "llm_as_a_judge": true,  {# 是否使用LLM作为裁判 #}
    "judge_system_prompt": "你是一个智能助手，请判断答案跟问题是否匹配并给出0-10的得分，注意只输出得分不需要过程，评判规则：答案跟问题完全相关且没有逻辑错误得10分，不符合依次扣分。",  {# 裁判系统提示词 #}
    "judge_prompt": "问题: {question}\n\n预测答案: {pred}\n\n你给出的得分是：",  {# 裁判提示词 #}
    "metric_list": ["score"] {# 度量指标 #}
}
{% endmacro %}

{# 2. 生成提示词 #}
{% macro gen_prompt(system_prompt, history, user_prompt) %}
{% set final_user_prompt = user_prompt %}
{% if history %}
    {% set history_prompt = '' %}
    {% for h in history %}
        {% for k, v in h.items() %}
            {% set history_prompt = history_prompt ~ k ~ ': ' ~ v ~ '\n' %}
        {% endfor %}
    {% endfor %}
    {% set final_user_prompt = "用户的对话内容如下：\n" ~ history_prompt ~ "user: " ~ user_prompt ~ "\n" %}
{% endif %}
{
    "system_prompt": {{ system_prompt | to_json }},
    "user_prompt": {{ final_user_prompt | to_json }}
}
{% endmacro %}

{# 3. 获取标准答案 #}
{% macro get_gold_answer(input_d) %}
{{ input_d.get('answer', '') }}
{% endmacro %}

{# 4. 解析预测结果 #}
{% macro parse_pred_result(result) %}
{{result | trim}}
{% endmacro %}

{# 5. 比较预测结果和标准答案 #}
{% macro match(gold, pred) %}
{}
{% endmacro %}

{# 6. LLM裁判响应解析，llm_as_a_judge会使用到 #}
{% macro llm_match(judge_response) %}
{% set match_result = judge_response | regex_search('(\d+)') %}
{% set res = match_result if match_result else '0' %}
{
    "score": {{ res }}
}
{% endmacro %}

{# 7. 计算评估指标 #}
{# 可以为空，为空时计算伤处指标在数据子集的均值#}
```

### RAG数据集
RAG评估时支持两种jsonl格式的数据集，一种是包含了通过各种策略召回的上下文片段及大模型最终的回答，一种是不包含二者，仅有用户问题和参考答案。
如果你已有完备的RAG系统，一般会开放接口可以获取到上下文片段和最终答案，此时可以选择后者配合jinja2即可。
数据集字段解释：
- user_input: 一般是规整后的完整问题
- retrieved_contexts: RAG系统通过向量+重排等策略召回的上下文片段
- response: RAG系统对问题的回答
- reference: 参考答案，来源于标注

RAG评估使用的是ragas框架，评估指标参考:[Ragas指标](https://docs.ragas.io/en/latest/concepts/metrics/available_metrics/)

jinja2要求实现get_context和get_response两个宏，内置了http.request函数以及fromjson、tojson过滤器。你可以参考：

```jinja2
{% macro get_context(user_input) %}
    {# 发送GET请求到搜索API并获取上下文 #}
    {% set url = "http://127.0.0.1:5001/api/retrieve?query=" + user_input|urlencode %}
    {% set headers = {"Content-Type": "application/json"} %}
    {% set raw_response = http.request(url=url, method='GET', headers=headers) %}
    
    {# 尝试解析JSON响应 #}
    {% set response_json = raw_response|fromjson %}
    
    {# 提取搜索结果 - 假设API返回格式为 {"results": [...]} #}
    {% if response_json and response_json.results %}
        {# 返回结果列表作为上下文 #}
        {{ response_json.results|tojson }}
    {% else %}
        {# 返回空列表作为后备 #}
        []
    {% endif %}
{% endmacro %}

{% macro get_response(user_input, context) %}
    {# 发送POST请求到生成API获取回答 #}
    {% set url = "http://127.0.0.1:5001/api/generate" %}
    {% set headers = {"Content-Type": "application/json"} %}
    {% set data = {
        "query": user_input,
        "context": context,
        "max_tokens": 500,
        "temperature": 0.7
    } %}
    
    {% set raw_response = http.request(url=url, method='GET', headers=headers, data=data) %}
    
    {# 尝试解析JSON响应 #}
    {% set response_json = raw_response|fromjson %}
    
    {# 提取生成的文本 - 假设API返回格式为 {"response": "..."} #}
    {% if response_json and response_json.response %}
        {{ response_json.response }}
    {% elif response_json and response_json.generated_text %}
        {{ response_json.generated_text }}
    {% else %}
        {# 如果解析失败，返回原始响应 #}
        {{ raw_response }}
    {% endif %}
{% endmacro %}
```

### 项目结构

```
llm-eva/
├── app/                    # 应用主目录
│   ├── models/            # 数据模型
│   ├── routes/            # 路由定义
│   ├── services/          # 业务逻辑
│   ├── templates/         # HTML模板
│   └── static/            # 静态资源
├── migrations/            # 数据库迁移
├── tests/                 # 测试文件
├── docker/               # Docker配置
├── requirements.txt      # Python依赖
└── run.py               # 启动文件
```

### 技术栈

- **后端**：Flask + SQLAlchemy + MySQL
- **前端**：HTML + JavaScript + DaisyUI
- **评估引擎**：EvalScope
- **任务队列**：Celery
- **部署**：Docker + Docker Compose

支持自定义基准的开发和集成。

## 🤝 贡献指南

我们欢迎所有形式的贡献！

### 如何贡献

1. Fork 这个项目
2. 创建你的特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交你的改动 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开一个 Pull Request

### 开发规范

- 遵循 PEP 8 Python 代码规范
- 添加适当的测试用例
- 更新相关文档
- 确保所有测试通过


## 🆘 常见问题

### Q: 如何添加新的评估基准？
A: 可以通过使用[Jinja2](https://jinja.palletsprojects.com/en/stable/)模板来实现，也可以通过扩展 EvalScope 的适配器来添加自定义基准，可以参考[custom_dataset_adapter.py](https://github.com/justplus/llm-eval/blob/main/app/adapter/custom_dataset_adapter.py)。

### Q: 支持哪些模型API格式？
A: 支持 OpenAI 兼容的 API 格式，包括大部分主流大模型服务。

### Q: 如何处理大规模数据集？
A: 系统支持分批处理和异步任务，可以处理大规模评估任务。

### Q: 还支持哪些通用数据集？
参考[supported_dataset](https://evalscope.readthedocs.io/zh-cn/latest/get_started/supported_dataset.html#id2)

## 📄 开源协议

本项目基于 [MIT License](LICENSE) 开源协议。

## 🙏 致谢

- [EvalScope](https://github.com/modelscope/evalscope) - 提供强大的评估引擎
- [DaisyUI](https://daisyui.com/) - 优雅的UI组件库
- [Flask](https://flask.palletsprojects.com/) - 轻量级Web框架

---

<div align="center">
如果这个项目对你有帮助，请给一个 ⭐️！
</div>

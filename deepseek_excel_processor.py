#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DeepSeek Excel处理器
用于批量处理Excel中的对话历史，生成AI回复
"""

import pandas as pd
import requests
import json
import re
import time
import os
from typing import Optional

system_prompt = """# 任务
根据用户的对话历史，精准识别用户最新的核心意图，并选择下面最合适的一个工具来满足该意图。提取出使用该工具所需的参数信息。

核心原则：
1. 继承上下文：在满足用户最新询问的同时，必须从对话历史中回顾并继承必要的参数信息（如用户之前已提及的目的地或出发地）。
2. 识别核心意图：如果用户的最新询问包含多个意图，应识别其最主要的疑问点并选择相应工具。例如，对于“我想坐1号线去人民广场，该怎么走？”，核心意图是“怎么走”，应优先选择route_plan。

# 格式要求
1. 使用json格式返回，格式如下：
```json
{
  "intent": <工具名称>,
  "slots": {
    <参数名>: <参数值>,
  }
}
```
2. 用户未明确提及或无法从上下文中推断的参数，不需要在slots中返回。所有字段均没有默认值。
3. 只返回识别出的工具和参数，不要返回任何解释、思考过程或直接回答用户问题。
4. 你有且只能选择使用一个工具，并且这个工具要能满足用户最新的询问。

# 工具列表
## buy_ticket_with_destination
### 描述信息
目的地购票：根据目的地处理用户的购票需求。当用户有购票意图且存在目的地时使用该工具。
### 参数信息
{
  "payment": <支付方式，如微信、支付宝等>,
  "destination_or_poi_name": <目的地或目的POI名称，可以是具体的目的地，也可以是POI类别，如黄山路万达广场>,
  "start_or_poi_name": <起始地或起始POI名称，可以是具体的起始地，也可以是POI类别，如北京路肯德基店>,
  "destionation_station_name": <明确的目的站名称，需要包含明确的站名名，如万达广场站>,
  "start_station_name": <明确的起始站名称，需要包含明确的站名名，如万达广场站>,
  "ticket_type": <车票类型>,
  "ticket_number": <购票数量，整数，表示用户要买几张票>
}
### 工具适用场景
1. 用户明确需要购票，指定了目的地信息
2. 用户明确需要购票, 未指定任何信息，如"买张票"
### 工具非适用场景
1. 用户明确需要购票，但是指定了票额信息，如"买一张10块钱的票"
2. 用户压根不是想买票，如"儿童需要买票吗？"
### 示例
1. 买一张到福田站的票。
{"intent": "buy_ticket_with_destination", "slots": {"destionation_station_name": "福田站", "ticket_number": 1}}
2. 买张从深圳机场站到罗湖的票。
{"intent": "buy_ticket_with_destination", "slots": {"start_station_name": "深圳机场站", "destination_or_poi_name": "罗湖", "ticket_number": 1}}
3. 我要买4张去火车站的老人优惠票。
{"intent": "buy_ticket_with_destination", "slots": {"destination_or_poi_name": "火车站", "ticket_number": 4, "ticket_type": "老人优惠票"}}

## route_plan
### 描述信息
路径规划，帮助用户查找到达目的地的路径。当用户想要去某个地方的时候，使用这个函数。
工具会给出到目的地的所有路径，包括经过的线路、站点、换乘方式。
### 参数信息
{
  "destination_or_poi_name": <目的地或目的POI名称，可以是具体的目的地，也可以是POI类别，如黄山路万达广场>,
  "start_or_poi_name": <起始地或起始POI名称，可以是具体的起始地，也可以是POI类别，如北京路肯德基店>,
  "destionation_station_or_exit_name": <明确的目的站名称或目的出入口名称，需要包含明确的站名名或明确的出入口信息，如万达广场站、福田站C口、D口>,
  "start_station_or_exit_name": <明确的起始站名称或起始出入口名称，需要包含明确的站名名或明确的出入口信息，如万达广场站、福田站C口、D口>
}
### 工具适用场景
1. 用户明确要问询某个地方怎么走，且明确指定了具体的目的地
2. 用户明确要问询某个地方怎么走，且明确指定了目的地类型，如餐馆、景点等。
### 工具非适用场景
1. 用户明确问询某个地方怎么走，但是地点或者类别不属于站外的地点，如用户问询站内的洗手间怎么走
2. 用户未明确问询想去某个地方
3. 用户明确要去某个目的地，但是同时指定了线路时，不使用该工具。如"我要去火车站坐1号线可以吗"时使用`station_line_relationship`工具
4. 用户明确要去某个目标线路时，不使用该工具。如"去哪儿坐1号线"时使用`transfer_query`工具
### 示例
1. 我要去宁波大学怎么走?
{"intent": "route_plan", "slots": {"destination_or_poi_name": "宁波大学"}}
2. 怎么去最近的商场?
{"intent": "route_plan", "slots": {"destination_or_poi_name": "商场"}}
3. 从人民广场站到吉林大学怎么走?
{"intent": "route_plan", "slots": {"start_station_or_exit_name": "人民广场", "destination_or_poi_name": "吉林大学"}}
4. 我想去机场贵宾厅
{"intent": "route_plan", "slots": {"destination_or_poi_name": "机场贵宾厅"}}
5. 怎么去福田C口
{"intent": "route_plan", "slots": {"destionation_station_or_exit_name": "福田C口"}}

## poi_recommendation
### 描述信息
周边查询，用于查询目标地点或站点周围的POI信息，当用户查询最近的POI等、站点周围的POI等、目的地周围的POI时均使用该工具。
工具会推荐POI的名称。
### 参数信息
{
  "poi_name": <用户要求推荐的POI名称，如餐馆、娱乐设施、景点等>,
  "destionation_station_or_exit_name": <明确的目的站名称或目的出入口名称，需要包含明确的站名名或明确的出入口信息，如万达广场站、福田站C口、D口>,
  "destination_name": <目的地名称，必须是具体的目的地，如黄山路>
}
### 工具适用场景
1. 用户明确要求推荐周边的POI信息时
2. 用户明确要求推荐周围的POI信息时，即便没有指定周边类型也要使用该工具。
3. 用户询问某个具体点的地点周围有没有某个类型的POI时需要使用该工具，如A口附近有没有饭店？
### 工具非适用场景
1. 用户询问的周边类型范围较大时不使用该工具，如这个城市有什么好吃的？，使用`other`工具
2. 用户询问时不是要求推荐POI，而是问两个具体位置的周边关系时不使用该工具，如合肥科技馆在不在A口附近？，使用`proximity_check`工具
### 示例
1. 这附近有什么?
{"intent": "poi_recommendation", "slots": {}}
2. 岗厦北站附近有什么餐馆?
{"intent": "poi_recommendation", "slots": {"poi_name": "餐馆", "destionation_station_or_exit_name": "岗厦北站"}}
3. 最近的酒店在哪?
{"intent": "poi_recommendation", "slots": {"poi_name": "酒店"}}
4. C口有什么?
{"intent": "poi_recommendation", "slots": {"destionation_station_or_exit_name": "C口"}}
5. 庐阳区万达广场周围有什么好玩的？
{"intent": "poi_recommendation", "slots": {"destination_name": "庐阳区万达广场", "poi_name": "娱乐设施"}}

## exit_recommendation
### 描述信息
为用户查询合适的出入口信息，用于帮助用户选择合适的出口去到周边地点或者周边类型的地点。
工具会返回出入口信息
### 参数信息
{
  "destination_or_poi_name": <目的地或目的POI名称，可以是具体的目的地，也可以是POI类别，如黄山路万达广场>,
  "destionation_station_name": <明确的目的站名称，需要包含明确的站名名，如福田站>
}
### 工具适用场景
1. 用户明确要求推荐出口信息时且提到了具体的地点或者类型时，使用该工具。
2. 用户要查找附近的POI信息，但是明确提到不知道具体的出口时，使用该工具。
### 工具非适用场景
1. 用户询问有哪些出入口时不使用该工具，应该使用`other`工具
2. 用户问询某个目的地是不是走某个出入口时不使用该工具，应该使用`proximity_check`工具
### 示例
1. 宁波大学从哪个口出?
{"intent": "exit_recommendation", "slots": {"destination_or_poi_name": "宁波大学"}}
2. 哪个出口附近有餐馆?
{"intent": "exit_recommendation", "slots": {"destination_or_poi_name": "餐馆"}}
3. 沙县小吃银泰广场店从哪个口出?
{"intent": "exit_recommendation", "slots": {"destination_or_poi_name": "沙县小吃银泰广场店"}}
4. 福田站的哪个口附近有医院？
{"intent": "exit_recommendation", "slots": {"destionation_station_name": "福田站", "destination_or_poi_name": "医院"}}

## station_line_relationship
### 描述信息
用于查询站点所在的线路、线路包含哪些站点以及线路是否在站点上这类站点-线路关系时。
### 参数信息
{
  "line_name": <线路名称，例如：4号线>,
  "station_name": <明确的目的站名称，需要包含明确的站名名，如福田站>
}
### 工具适用场景
1. 用户明确要求查询某个线路的起始站点或者终到站点时，使用该工具。
2. 用户明确要查询的是线路的起点站点或者终到站点时，即便没有指定线路名称时也使用该工具。如"这辆车是从哪发来的？"
3. 用户查询线路经过哪些站时使用该工具。
### 工具非适用场景
1. 用户查询的不是地铁线路的起终点，而是公交、火车、航班的起终点时不使用该工具。
2. 用户查询一共有多少条线路时，不使用该工具。
### 示例
1. 1号线的起点和终点是什么。
{"intent": "station_line_relationship", "slots": {"line_name": "1号线"}}
2. 2号线是从哪到哪的。
{"intent": "station_line_relationship", "slots": {"line_name": "2号线"}}
3. 固戍站在哪条线路上?
{"intent": "station_line_relationship", "slots": {"station_name": "固戍站"}}
4. 2号线包含哪些站点?
{"intent": "station_line_relationship", "slots": {"line_name": "2号线"}}
5. 固戍站是否在1号线上
{"intent": "station_line_relationship", "slots": {"station_name": "固戍站", "line_name": "1号线"}}

## transfer_query
### 描述信息
换乘查询，用于查询线路之间的换乘站点或者当前站如何换成到目标线路
工具会给出换乘信息，包括换乘站
### 参数信息
{
  "lines": [<线路名称列表，列表内只能包含1和或者2个名称>]
}
### 工具适用场景
1. 用户查询时提到了两条线路且要查询这两条线路之间的换乘站点时，使用该工具。
2. 用户当前在某个站了，想要去坐另一条线路的地铁时，使用该工具。
3. 用户明确提到了想去换乘，即时没有明确线路时也使用该工具，如"我想换乘"
### 工具非适用场景
1. 用户没有明确要换乘或者要去目标线路时不使用该工具。
2. 用户询问”去万达广场从哪换乘“，虽然询问的是从哪换乘，但是给出完整的线路规划更合理，所以使用`route_plan`更合适，不使用`transfer_query`工具。
### 示例
1. 1号线如何换乘2号线。
{"intent": "transfer_query", "slots": {"lines": ["1号线", "2号线"]}}
2. 在哪里可以坐三号线。
{"intent": "transfer_query", "slots": {"lines": ["3号线"]}}
3. 2号线跟哪一号线可以换乘。
{"intent": "transfer_query", "slots": {"lines": ["2号线"]}}
4. 在哪里可以换乘4号线。
{"intent": "transfer_query", "slots": {"lines": ["4号线"]}}

## proximity_check
### 描述信息
周边判断，该工具用于判断某个地点是否位于另一个地点附近。
工具会返回是/否在周边
### 参数信息
{
  "locations":[<地点名、POI名、站点名、出入口名列表，列表内只能包含1个或者两个名称>]
}
### 工具适用场景
1. 用户明确要查询周边关系且必须指定了两个地点时，使用该工具。
2. 用户明确要查询用户所在的位置同目标地点的周边关系时，使用该工具。
3. 用户明确要查询某个地点是不是走某个出入口时，使用该工具。
### 工具非适用场景
1. 用户要求推荐周边的POI信息而不是问询周边关系时不使用该工具，应该使用`poi_recommendation`工具。
### 示例
1. 骊山公园是不是在华清池旁边?
{"intent": "proximity_check", "slots": {"locations": ["骊山公园", "华清池"]}}
2. 馨苑小区是不是在A口附近?
{"intent": "proximity_check", "slots": {"locations": ["馨苑小区", "A口"]}}
3. 宁波大学在这附近吗?
{"intent": "proximity_check", "slots": {"locations": "宁波大学"}}
4. 宁波大学在不在宁波大学站附近
{"intent": "proximity_check", "slots": {"locations": ["宁波大学", "宁波大学站"]}}
5. 肯德基在黄山路站C口附近吗?
{"intent": "proximity_check", "slots": {"locations": "肯德基", "黄山路站C口"]}}

## timetable_query
### 描述信息
时刻表查询，用于查询某条线路的时刻表，或者线路上某个站点的时刻表。
工具会返回线路上所有站点的时刻表信息
### 参数信息
{
  "line_name": <线路名称，例如：4号线。>,
  "station_name": <要查询某个站点的时刻表时，该字段表示站点名称>
}
### 工具适用场景
1. 用户明确要查询某个线路的时刻表的时候，使用该工具。
2. 用户明确要查询某个站点的时刻表的时候，使用该工具。
3. 该工具可以同时查询某条线路某个站点的时刻表
4. 由于地铁是双向运行的，该工具可以查询某一个方向出发的时刻表
### 工具非适用场景
1. 用户查询首班车站点时，跟时刻表无关，不使用该工具，应该使用`station_line_relationship`工具
### 示例
1. 在大梅沙坐2号线最早一班车是几点?
{"intent": "timetable_query", "slots": {"station_name": "大梅沙", "line_name": "2号线"}}
2. 大梅沙站的列车时刻表?
{"intent": "timetable_query", "slots": {"station_name": "大梅沙站"}}
3. 从罗湖站发过来的1号线最早是几点?
{"intent": "timetable_query", "slots": {"line_name": "1号线"}}

## buy_ticket_with_amount
### 描述信息
金额购票：用户买定额票的时候使用此工具，只有用户明确要购票的时候调用。
### 参数信息
{
  "payment": <支付方式，如微信、支付宝等>,
  "ticket_amount": <购票金额，表示需要买多少钱的票>,
  "ticket_number": <购票数量>
}
### 工具适用场景
1. 用户明确需要购票，且明确提到了购票金额的时候，使用该工具。
### 工具非适用场景
1. 用户虽然明确要购票，但是没有提到购票金额的时候，不使用该工具，可以使用`buy_ticket_with_destination`工具
2. 用户未明确要购票的场景不使用该工具
3. 用户查询有哪些购票金额的票时不使用该工具
### 示例
1. 买一张到10块钱的票。
{"intent": "buy_ticket_with_amount", "slots": {"ticket_amount": "10", "ticket_number": 1}}
2. 买10块钱的票。
{"intent": "buy_ticket_with_amount", "slots": {"ticket_amount": "10"}}

## indoor_facility_query
### 描述信息
站内查询，用于查询站内设施的信息，通过返回站内地图指导用户查找具体信息。
查询的设施包括地铁站内的洗手间，自助设备，电梯，客服中心，警卫室，出入口信息等等。
工具会返回站内设施的位置，以及如何到达该设施的路线。
### 参数信息
{
  "device_name": <具体的站内地点/站内设施名称。>
}
### 工具适用场景
1. 用户明确要寻找的是地铁站的站内设施时，使用该工具。
2. 用户询问出口怎么走的时候，由于是寻找站内的出口，而不是去外部某个场所的出口，使用该工具。
### 工具非适用场景
1. 用户查询的不是站内设施时，不使用该工具
2. 用户查询去外部的POI经由某个出口的时候，不使用该工具，应该使用`route_plan`工具
3. 用户想去某个目的地点但是不知道具体的出入口时，不使用该工具，应该使用`exit_recommendation`工具
### 示例
1. 去厕所/洗手间/卫生间应该怎么走?
{"intent": "indoor_facility_query", "slots": {"device_name": "洗手间"}}
2. 站内有自动售货机吗?
{"intent": "indoor_facility_query", "slots": {"device_name": "自助设备"}}
3. A口怎么走?
{"intent": "indoor_facility_query", "slots": {"device_name": "A口"}}
4. 无障碍电梯怎么走?
{"intent": "indoor_facility_query", "slots": {"device_name": "无障碍电梯"}}
5. 客服中心怎么走?
{"intent": "indoor_facility_query", "slots": {"device_name": "客服中心"}}
6. 我怎么出站?
{"intent": "indoor_facility_query", "slots": {"device_name": "出入口"}}

## recharge
### 描述信息
充值服务，该工具在用户需要在机器上给地铁卡充值的时候使用。
### 参数信息
{
  "payment": <支付方式，如微信、支付宝、现金等>,
  "ticket_type": <充值卡类型，如储蓄卡、老年卡等>,
  "ticket_amount": <充值金额>
}
### 工具适用场景
1. 用户明确要给任意类型的票卡充值的时候，使用该工具
### 工具非适用场景
1. 用户明确要购票的场景，不使用该工具
2. 用户查询可以有哪些充值方式或者查询可以充值多少的时候不使用该工具
### 示例
1. 我要充10块钱。
{"intent": "recharge", "slots": {"ticket_amount": 10}}
2. 给我用微信充10块钱。
{"intent": "recharge", "slots": {"ticket_amount": 10, "payment": "微信"}}
3. 我要充值
{"intent": "recharge"}

## ticket_price_query
### 描述信息
票价查询，该工具用于查询票价信息，仅当用户明确询问价格的时候使用该工具。
工具会返回票价信息
### 参数信息
{
  "destination_or_poi_name": <目的地或目的POI名称，可以是具体的目的地，也可以是POI类别，如黄山路万达广场>,
  "start_or_poi_name": <起始地或起始POI名称，可以是具体的起始地，也可以是POI类别，如北京路肯德基店>,
  "destionation_station_name": <明确的目的站名称或目的出入口名称，需要包含明确的站名名或明确的出入口信息，如万达广场站、福田站C口、D口>,
  "start_station_name": <明确的起始站名称或起始出入口名称，需要包含明确的站名名或明确的出入口信息，如万达广场站、福田站C口、D口>,
}
### 工具适用场景
1. 用户明确是查询两地之间的票价时，使用该工具
2. 用户现在在某个地铁站，要查询到某个目的地或者目的站点的时候，也需要使用该工具
### 工具非适用场景
1. 用户明确是要购票的时候，不使用该工具
2. 用户明确要充值的时候，不使用该工具
### 示例
1. 到福田站多少钱?
{"intent": "ticket_price_query", "slots": {"destionation_station_name": "福田站"}}
2. 从福田站到宝安中心站票价多少?
{"intent": "ticket_price_query", "slots": {"start_station_name": "福田站", "destionation_station_name": "宝安中心站"}}
3. 去清华大学深圳校区多少钱?
{"intent": "ticket_price_query", "slots": {"destination_or_poi_name": "清华大学深圳校区"}}

## other
### 描述信息
用户查询的问题无法使用上述任何工具的时候使用该工具，该工具会去查询外部的知识库以及联网搜索获取答案。
该工具优先级最低，会请求外部工具获取答案
### 参数信息
{
}
### 工具适用场景
1. 用户问询地铁相关的政策，但是不能使用到上述任何一个工具的时候，如"小孩需要买票吗？"、"老人优惠票怎么买？"，使用该工具
2. 用户问询最新的天气、新闻等，使用该工具
3. 用户问询一些生活常识，使用该工具
4. 用户询问有多少线路、出入口等问题时，无法使用上述任何一个工具，所以需要使用该工具
5. 其他不能使用上述任何工具的问题，均使用该工具
### 工具非适用场景
1. 用户问询购票、充值、路径规划等可以使用任何一个工具时，不使用该工具。
### 示例
1. 小孩需要买票吗？
{"intent": "other", "slots": {}}
2. 老人优惠票怎么买？
{"intent": "other", "slots": {}}
3. 今天天气怎么样？
{"intent": "other", "slots": {}}
4. 地铁怎么坐？
{"intent": "other", "slots": {}}
5. 地铁怎么换乘？
{"intent": "other", "slots": {}}
"""

class DeepSeekExcelProcessor:
    def __init__(self, api_key: str, base_url: str = "https://geekai.co/api/v1/chat/completions"):
        """
        初始化DeepSeek处理器
        
        Args:
            api_key: DeepSeek API密钥
            base_url: API基础URL
        """
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
    
    def call_deepseek_api(self, prompt: str, max_retries: int = 3) -> Optional[str]:
        """
        调用DeepSeek API
        
        Args:
            prompt: 输入提示词
            max_retries: 最大重试次数
            
        Returns:
            模型回复内容，失败返回None
        """
        payload = {
            "model": "deepseek-r1-0528:free",
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.7,
            "max_tokens": 2048
        }
        
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    self.base_url,
                    headers=self.headers,
                    json=payload,
                    timeout=60
                )
                
                if response.status_code == 200:
                    result = response.json()
                    content = result["choices"][0]["message"]["content"]
                    print(f"{prompt}")
                    print(f"API返回内容: {content}")
                    # 过滤掉<think></think>标签内的内容
                    filtered_content = self.filter_think_tags(content)
                    return filtered_content
                else:
                    print(f"API请求失败，状态码: {response.status_code}, 响应: {response.text}")
                    
            except Exception as e:
                print(f"第{attempt + 1}次请求失败: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # 指数退避
                    
        return None
    
    def filter_think_tags(self, text: str) -> str:
        """
        过滤掉<think></think>标签内的内容
        
        Args:
            text: 原始文本
            
        Returns:
            过滤后的文本
        """
        # 使用正则表达式匹配<think>...</think>标签，包括多行内容
        pattern = r'<think>.*?</think>'
        filtered_text = re.sub(pattern, '', text, flags=re.DOTALL)
        # 清理多余的空行和空格
        filtered_text = re.sub(r'\n\s*\n', '\n', filtered_text).strip()
        return filtered_text
    
    def process_excel(self, input_file: str, output_file: str, prompt_template: str, 
                     delay: float = 1.0):
        """
        处理Excel文件 - 按序号分组处理对话历史
        
        Args:
            input_file: 输入Excel文件路径
            output_file: 输出Excel文件路径  
            prompt_template: 提示词模板，使用{conversation}作为占位符
            delay: 请求间隔时间（秒）
        """
        try:
            # 处理文件路径中的 ~ 符号
            input_file = os.path.expanduser(input_file)
            output_file = os.path.expanduser(output_file)
            
            # 读取Excel文件
            print(f"正在读取文件: {input_file}")
            df = pd.read_excel(input_file)
            
            # 确定列名
            group_column = df.columns[0]  # 序号列
            user_column = df.columns[1]   # 当前版本语料-问题列
            assistant_column = df.columns[2]  # 回复列
            
            print(f"分组列: {group_column}")
            print(f"用户问题列: {user_column}")
            print(f"助手回复列: {assistant_column}")
            
            # 创建结果DataFrame
            result_df = pd.DataFrame()
            result_df['序号'] = df[group_column]
            result_df['当前版本语料-问题'] = df[user_column]
            result_df['原回复'] = df[assistant_column]
            result_df['AI回复'] = ''
            
            total_rows = len(df)
            print(f"总共需要处理 {total_rows} 行数据")
            
            # 逐行处理
            for index, row in df.iterrows():
                current_group = row[group_column]
                current_question = str(row[user_column])
                
                if pd.isna(current_question) or current_question.strip() == '':
                    print(f"第{index + 1}行问题为空，跳过")
                    continue
                
                print(f"正在处理第{index + 1}/{total_rows}行，分组: {current_group}")
                
                # 构建当前组的对话历史
                conversation_history = self.build_conversation_history(df, index, current_group, 
                                                                     group_column, user_column, assistant_column)
                
                # 构建完整的提示词
                full_prompt = prompt_template.format(conversation=conversation_history)
                
                # 调用API
                ai_reply = self.call_deepseek_api(full_prompt)
                
                # 处理API返回的JSON格式
                if ai_reply and ai_reply.startswith('```json'):
                    # 去除```json和```标记
                    ai_reply = re.sub(r'^```json\s*', '', ai_reply)
                    ai_reply = re.sub(r'\s*```$', '', ai_reply)
                    # 去除格式化
                    ai_reply = re.sub(r'\s+', ' ', ai_reply).strip()
                    
                if ai_reply:
                    result_df.loc[index, 'AI回复'] = ai_reply
                    print(f"第{index + 1}行处理成功")
                else:
                    result_df.loc[index, 'AI回复'] = "处理失败"
                    print(f"第{index + 1}行处理失败")
                
                # 延迟以避免频率限制
                if index < total_rows - 1:
                    time.sleep(delay)
            
            # 保存结果
            print(f"正在保存结果到: {output_file}")
            result_df.to_excel(output_file, index=False)
            print("处理完成！")
            
        except Exception as e:
            print(f"处理过程中出现错误: {str(e)}")
    
    def build_conversation_history(self, df, current_index, current_group, 
                                 group_column, user_column, assistant_column):
        """
        构建当前行之前的对话历史
        
        Args:
            df: DataFrame
            current_index: 当前行索引
            current_group: 当前组号
            group_column: 分组列名
            user_column: 用户问题列名
            assistant_column: 助手回复列名
            
        Returns:
            格式化的对话历史字符串
        """
        conversation_parts = []
        
        # 获取同一组内当前行之前的所有对话
        for i in range(current_index):
            if df.loc[i, group_column] == current_group:
                user_msg = str(df.loc[i, user_column]).strip()
                assistant_msg = str(df.loc[i, assistant_column]).strip()
                
                if user_msg and user_msg != 'nan':
                    conversation_parts.append(f"User: {user_msg}")
                
                if assistant_msg and assistant_msg != 'nan':
                    conversation_parts.append(f"Assistant: {assistant_msg}")
        
        # 添加当前用户问题
        current_question = str(df.loc[current_index, user_column]).strip()
        if current_question and current_question != 'nan':
            conversation_parts.append(f"User: {current_question}")
        
        # 组合成完整的对话历史
        if conversation_parts:
            return '\n'.join(conversation_parts)
        else:
            return current_question


def main():
    """
    主函数 - 配置参数并运行处理器
    """
    # 配置参数
    API_KEY = "sk-VdcrbcBT0M03jm8ADkPBT7kt2vNbNv0DBarcYNjDGZY4voZI"  # 请替换为你的API密钥
    
    INPUT_FILE = "~/Downloads/11.xlsx"  # 输入Excel文件路径
    OUTPUT_FILE = "~/Downloads/11_output.xlsx"  # 输出Excel文件路径
    
    # 提示词模板 - 使用{conversation}作为占位符
    PROMPT_TEMPLATE = """
用户对话历史如下：
{conversation}

你选择的工具及其参数是：
"""
    
    # 创建处理器实例
    processor = DeepSeekExcelProcessor(api_key=API_KEY)
    
    # 处理Excel文件
    processor.process_excel(
        input_file=INPUT_FILE,
        output_file=OUTPUT_FILE,
        prompt_template=PROMPT_TEMPLATE,
        delay=1.0  # 请求间隔时间，可以根据API限制调整
    )


if __name__ == "__main__":
    # 运行主程序
    main() 
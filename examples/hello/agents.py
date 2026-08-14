"""最小示例：文本处理流水线 Agent

展示如何用最少代码接入 MetroEngine —— 三个简单 Agent 组成一条线。
"""

from asman.agents.base import Agent
from asman.registry import register_agent


class KeywordAgent(Agent):
    def __init__(self):
        super().__init__("关键词提取", "keyword")

    async def execute(self, input_data, passenger_id):
        await super().execute(input_data, passenger_id)
        return {"keywords": ["agent", "metro", "pipeline"], "count": 3}


class SummaryAgent(Agent):
    def __init__(self):
        super().__init__("摘要", "summary")

    async def execute(self, input_data, passenger_id):
        await super().execute(input_data, passenger_id)
        return {"summary": "把复杂任务建模成地铁系统", "length": 11}


class TranslateAgent(Agent):
    def __init__(self):
        super().__init__("翻译", "translate")

    async def execute(self, input_data, passenger_id):
        await super().execute(input_data, passenger_id)
        return {"translated": "Model complex tasks as a metro system"}


def register_all():
    register_agent("keyword", KeywordAgent)
    register_agent("summary", SummaryAgent)
    register_agent("translate", TranslateAgent)

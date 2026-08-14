"""
ASMAN Agent Base
Agent基类：每个站点的处理逻辑
"""

import asyncio
from typing import Dict, Any, List


class Agent:
    """Agent基类"""

    def __init__(self, name: str, capability: str, config: Dict = None):
        self.name = name
        self.capability = capability
        self.config = config or {}
        self.processing_time = 0.5  # 模拟处理时间（秒）

    async def execute(self, input_data: Dict, passenger_id: str) -> Dict:
        """执行Agent核心逻辑"""
        # 模拟处理延迟
        await asyncio.sleep(self.processing_time)
        return {"status": "completed", "agent": self.name}

    async def slice(self, input_data: Dict) -> List[Dict]:
        """切片逻辑"""
        raise NotImplementedError(f"Agent {self.name} does not support slicing")

    async def merge(self, sub_results: List[Dict]) -> Dict:
        """重组逻辑"""
        raise NotImplementedError(f"Agent {self.name} does not support merging")

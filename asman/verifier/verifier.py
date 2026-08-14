"""Independent Verifier：独立于执行的评判（LLM-as-Judge）

执行与评分分离，避免执行 Agent「既当运动员又当裁判」。
无 judge 时保守返回通过分，不阻塞流程。
"""

from typing import Any, Dict, Optional

from ..core.models import QualityScores
from ..judge.judge import LLMJudge


class IndependentVerifier:
    def __init__(self, name: str = "Verifier", judge: Optional[LLMJudge] = None,
                 temperature: Optional[float] = None):
        self.name = name
        self.judge = judge
        self.temperature = temperature  # None → 用 judge 默认温度

    async def verify(self, output: Any, context: Dict, station_id: str) -> QualityScores:
        if self.judge is None:
            return QualityScores(0.85, 0.85, 0.85, 0.85, 0.85)
        return await self.judge.evaluate(output, context, station_id, temperature=self.temperature)

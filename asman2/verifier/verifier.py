"""ASMAN 2.0 Independent Verifier - Loop Engineering风格验证分离"""

import random
from typing import Dict, Any, List
from ..core.models import QualityScores


class IndependentVerifier:
    """
    独立Verifier Agent：执行与评分分离
    避免执行Agent"既当运动员又当裁判"
    支持多维度独立评估
    """

    def __init__(self, name: str = "Verifier"):
        self.name = name

    async def verify(self, output: Any, context: Dict, station_id: str) -> QualityScores:
        """
        独立验证产出
        真实系统应调用独立LLM（甚至不同模型）进行评估
        """
        # 模拟独立评估（与执行Agent不同的评分逻辑）
        base_scores = self._base_evaluate(output, context, station_id)

        # 引入"严格性偏移"：Verifier比执行Agent更严格
        strictness = 0.85  # Verifier打分会比执行Agent低约15%

        scores = QualityScores(
            coherence=min(base_scores.coherence * strictness + random.uniform(-0.05, 0.02), 1.0),
            creativity=min(base_scores.creativity * strictness + random.uniform(-0.05, 0.02), 1.0),
            consistency=min(base_scores.consistency * strictness + random.uniform(-0.05, 0.02), 1.0),
            grammar=min(base_scores.grammar * strictness + random.uniform(-0.05, 0.02), 1.0),
            engagement=min(base_scores.engagement * strictness + random.uniform(-0.05, 0.02), 1.0)
        )
        return scores

    def _base_evaluate(self, output: Any, context: Dict, station_id: str) -> QualityScores:
        """基础评估逻辑"""
        # 根据station_id调整权重
        weights = self._get_station_weights(station_id)

        # 模拟评估
        return QualityScores(
            coherence=random.uniform(0.75, 0.98) * weights.get("coherence", 1.0),
            creativity=random.uniform(0.70, 0.95) * weights.get("creativity", 1.0),
            consistency=random.uniform(0.72, 0.97) * weights.get("consistency", 1.0),
            grammar=random.uniform(0.80, 0.99) * weights.get("grammar", 1.0),
            engagement=random.uniform(0.70, 0.96) * weights.get("engagement", 1.0)
        )

    def _get_station_weights(self, station_id: str) -> Dict[str, float]:
        weights = {
            "S2": {"coherence": 0.8, "creativity": 1.2, "consistency": 0.8, "grammar": 0.6, "engagement": 1.0},
            "W1": {"coherence": 1.2, "creativity": 0.8, "consistency": 1.2, "grammar": 0.8, "engagement": 0.8},
            "W3": {"coherence": 1.0, "creativity": 1.0, "consistency": 1.0, "grammar": 1.2, "engagement": 1.0},
            "W4": {"coherence": 1.2, "creativity": 0.8, "consistency": 1.2, "grammar": 1.0, "engagement": 1.0},
            "V3": {"coherence": 1.0, "creativity": 0.8, "consistency": 1.2, "grammar": 0.8, "engagement": 1.2},
        }
        return weights.get(station_id, {k: 1.0 for k in ["coherence", "creativity", "consistency", "grammar", "engagement"]})
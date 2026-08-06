"""ASMAN 2.0 MoA Aggregator - Mixture of Agents投票聚合"""

from typing import Dict, List, Any
from ..core.models import QualityScores
from .verifier import IndependentVerifier


class MoAAggregator:
    """
    Mixture of Agents聚合器：
    多个Verifier独立评分，聚合器决定最终结果
    避免单一模型的评估偏见
    """

    def __init__(self, num_verifiers: int = 3):
        self.verifiers = [IndependentVerifier(f"Verifier_{i}") for i in range(num_verifiers)]
        self.num_verifiers = num_verifiers

    async def aggregate_verify(self, output: Any, context: Dict, station_id: str) -> QualityScores:
        """多Verifier投票"""
        # 并行调用多个Verifier
        scores_list = []
        for verifier in self.verifiers:
            score = await verifier.verify(output, context, station_id)
            scores_list.append(score)

        # 聚合策略：去掉最高最低，取中位数平均
        return self._aggregate_scores(scores_list)

    def _aggregate_scores(self, scores_list: List[QualityScores]) -> QualityScores:
        """聚合多个评分"""
        if len(scores_list) == 1:
            return scores_list[0]

        # 计算各维度中位数
        def median(values):
            s = sorted(values)
            n = len(s)
            if n % 2 == 1:
                return s[n // 2]
            return (s[n // 2 - 1] + s[n // 2]) / 2

        coherences = [s.coherence for s in scores_list]
        creativities = [s.creativity for s in scores_list]
        consistencies = [s.consistency for s in scores_list]
        grammars = [s.grammar for s in scores_list]
        engagements = [s.engagement for s in scores_list]

        return QualityScores(
            coherence=median(coherences),
            creativity=median(creativities),
            consistency=median(consistencies),
            grammar=median(grammars),
            engagement=median(engagements)
        )
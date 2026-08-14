"""MoA Aggregator：多个 Verifier 独立评分取中位数

避免单一评判模型的偏见。num_verifiers=1 时为单 judge；
>1 时用不同温度采样多个视角，聚合去最高最低取中位数。
"""

from typing import Any, Dict, List, Optional

from ..core.models import QualityScores
from ..judge.judge import LLMJudge
from .verifier import IndependentVerifier


class MoAAggregator:
    def __init__(self, judge: Optional[LLMJudge] = None, num_verifiers: int = 1):
        self.num_verifiers = max(1, num_verifiers)
        # 多次采样时的温度梯度，引入评判多样性
        temps = [None] if self.num_verifiers == 1 else [0.0, 0.2, 0.4, 0.6][:self.num_verifiers]
        self.verifiers = [
            IndependentVerifier(f"Verifier_{i}", judge, t)
            for i, t in enumerate(temps)
        ]

    async def aggregate_verify(self, output: Any, context: Dict,
                               station_id: str) -> QualityScores:
        scores_list: List[QualityScores] = []
        for verifier in self.verifiers:
            scores_list.append(await verifier.verify(output, context, station_id))
        return self._aggregate_scores(scores_list)

    def _aggregate_scores(self, scores_list: List[QualityScores]) -> QualityScores:
        if len(scores_list) == 1:
            return scores_list[0]

        def median(values):
            s = sorted(values)
            n = len(s)
            if n % 2 == 1:
                return s[n // 2]
            return (s[n // 2 - 1] + s[n // 2]) / 2

        return QualityScores(
            coherence=median([s.coherence for s in scores_list]),
            creativity=median([s.creativity for s in scores_list]),
            consistency=median([s.consistency for s in scores_list]),
            grammar=median([s.grammar for s in scores_list]),
            engagement=median([s.engagement for s in scores_list]),
        )

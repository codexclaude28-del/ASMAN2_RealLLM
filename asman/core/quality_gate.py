"""Quality Gate：站点质检门

评分由 LLM-as-Judge 承担（见 judge/ 与 verifier/），
此处只做「是否达标」判定与最弱维度分析。
"""

from ..core.models import QualityScores


class QualityGate:
    def __init__(self, station_id: str, threshold: float = 0.85):
        self.station_id = station_id
        self.threshold = threshold

    def judge(self, scores: QualityScores) -> bool:
        """平均分是否达标"""
        return scores.average() >= self.threshold

    def find_weakest(self, scores: QualityScores) -> str:
        dims = {
            "coherence": scores.coherence,
            "creativity": scores.creativity,
            "consistency": scores.consistency,
            "grammar": scores.grammar,
            "engagement": scores.engagement,
        }
        return min(dims, key=dims.get)

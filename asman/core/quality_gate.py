"""Quality Gate：站点质检门

评分由 LLM-as-Judge 承担（见 judge/ 与 verifier/），
是否达标的阈值判断在站点处理路径完成
（权威来源：ticket.config.quality_threshold），
此处只做最弱维度分析（用于回环修正提示）。
"""

from ..core.models import QualityScores


class QualityGate:
    def __init__(self, station_id: str):
        self.station_id = station_id

    def find_weakest(self, scores: QualityScores) -> str:
        dims = {
            "coherence": scores.coherence,
            "creativity": scores.creativity,
            "consistency": scores.consistency,
            "grammar": scores.grammar,
            "engagement": scores.engagement,
        }
        return min(dims, key=dims.get)

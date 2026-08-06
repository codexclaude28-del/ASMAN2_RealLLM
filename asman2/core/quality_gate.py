"""
ASMAN Quality Gate
质量门控环：每个站点出站前自动质检
"""

import random
from typing import Dict, Any
from .models import Passenger, QualityScores, GateResult


class QualityEvaluator:
    """质量评估器：多维度评分"""

    async def evaluate(self, output: Any, context: Dict, station_id: str) -> QualityScores:
        """
        评估产出质量
        真实系统应使用LLM-as-Judge或专用评估模型
        此处用模拟评分演示架构
        """
        # 模拟：根据station_id决定评估维度权重
        weights = self._get_weights(station_id)

        # 模拟评分（真实系统应调用评估Agent）
        scores = QualityScores(
            coherence=self._score_dimension("coherence", output, context) * weights["coherence"],
            creativity=self._score_dimension("creativity", output, context) * weights["creativity"],
            consistency=self._score_dimension("consistency", output, context) * weights["consistency"],
            grammar=self._score_dimension("grammar", output, context) * weights["grammar"],
            engagement=self._score_dimension("engagement", output, context) * weights["engagement"]
        )
        return scores

    def _get_weights(self, station_id: str) -> Dict[str, float]:
        weights = {
            "default": {"coherence": 1.0, "creativity": 1.0, "consistency": 1.0, 
                       "grammar": 1.0, "engagement": 1.0},
            "S2": {"coherence": 0.8, "creativity": 1.2, "consistency": 0.8,
                   "grammar": 0.6, "engagement": 1.0},  # 脑暴站看重创意
            "W1": {"coherence": 1.2, "creativity": 0.8, "consistency": 1.2,
                   "grammar": 0.8, "engagement": 0.8},  # 大纲站看重结构和一致性
            "W3": {"coherence": 1.0, "creativity": 1.0, "consistency": 1.0,
                   "grammar": 1.2, "engagement": 1.0},  # 写作站看重文笔
            "W4": {"coherence": 1.2, "creativity": 0.8, "consistency": 1.2,
                   "grammar": 1.0, "engagement": 1.0},  # 润色站看重一致性
            "V3": {"coherence": 1.0, "creativity": 0.8, "consistency": 1.2,
                   "grammar": 0.8, "engagement": 1.2},  # 视频站看重音画同步
        }
        return weights.get(station_id, weights["default"])

    def _score_dimension(self, dimension: str, output: Any, context: Dict) -> float:
        """模拟单维度评分"""
        # 真实系统应调用LLM评估
        base = random.uniform(0.75, 0.98)
        # 模拟偶尔的低分（触发重试/回环）
        if random.random() < 0.05:
            base = random.uniform(0.5, 0.75)
        return round(base, 2)


class QualityGate:
    """
    站点安检门：产出不达标，不允许出站
    """

    def __init__(self, station_id: str, threshold: float = 0.85):
        self.station_id = station_id
        self.threshold = threshold
        self.evaluator = QualityEvaluator()
        self.max_retry = 3

    async def check(self, passenger: Passenger) -> GateResult:
        """检查乘客产出质量"""
        output_key = f"output_{self.station_id}"
        output = passenger.baggage.get(output_key)

        if output is None:
            # 无产出，直接失败
            return GateResult.RETRY

        # 执行质量评估
        scores = await self.evaluator.evaluate(
            output=output,
            context=passenger.baggage,
            station_id=self.station_id
        )

        # 记录评分
        passenger.quality_scores[self.station_id] = scores
        avg_score = scores.average()

        if avg_score >= self.threshold:
            return GateResult.PASS

        # 不达标：分析最弱维度
        weakest = self._find_weakest(scores)
        passenger.failed_gates.append(f"{self.station_id}:{weakest}")

        # 检查重试次数
        retry_count = passenger.get_retry_count(self.station_id)
        if retry_count < self.max_retry:
            passenger.increment_retry(self.station_id)
            return GateResult.RETRY

        # 重试次数用尽：触发回环
        return GateResult.BACKLOOP

    def _find_weakest(self, scores: QualityScores) -> str:
        """找出最弱的维度"""
        dims = {
            "coherence": scores.coherence,
            "creativity": scores.creativity,
            "consistency": scores.consistency,
            "grammar": scores.grammar,
            "engagement": scores.engagement
        }
        return min(dims, key=dims.get)

    def get_upstream_fix(self, weakest: str, station_id: str) -> str:
        """
        根据最弱维度，决定回环到哪个上游站点
        这是自治系统的关键：系统自己知道该回退到哪里
        """
        fix_map = {
            "S2": {"coherence": "S1", "creativity": "S2", "consistency": "S1"},
            "W1": {"coherence": "W1", "creativity": "S2", "consistency": "W1"},
            "W3": {"coherence": "W1", "creativity": "W3", "consistency": "W1", 
                   "grammar": "W3", "engagement": "W3"},
            "W4": {"coherence": "W3", "creativity": "W3", "consistency": "W1",
                   "grammar": "W4", "engagement": "W3"},
            "V3": {"coherence": "D2", "creativity": "D2", "consistency": "D1",
                   "grammar": "V2", "engagement": "D2"}
        }
        return fix_map.get(station_id, {}).get(weakest, station_id)

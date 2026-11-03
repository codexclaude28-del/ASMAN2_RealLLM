"""LLM-as-Judge：独立模型的结构化质量评判

用独立于生成模型的 LLM 对站点产出做五维评分，
替代演示版的 random 评分。mock 模式或调用失败时降级到启发式评分。
"""

import json
from typing import Dict, Any, Optional

from ..core.models import QualityScores
from ..llm.client import LLMClient
from .schema import JUDGE_SYSTEM_PROMPT


class LLMJudge:
    def __init__(self, llm_client: Optional[LLMClient] = None,
                 model: str = "", temperature: float = 0.2, max_tokens: int = 500):
        self.llm_client = llm_client or LLMClient(provider="mock")
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    async def evaluate(self, output: Any, context: Dict, station_id: str,
                       temperature: Optional[float] = None) -> QualityScores:
        """评分入口；temperature 可覆盖默认值（用于 MoA 多次采样）"""
        prompt = self._build_prompt(output, context, station_id)

        if self.llm_client.provider == "mock":
            return self._heuristic_evaluate(output)

        try:
            resp = await self.llm_client.chat(
                system_prompt=JUDGE_SYSTEM_PROMPT,
                user_prompt=prompt,
                model=self.model or None,
                temperature=self.temperature if temperature is None else temperature,
                max_tokens=self.max_tokens,
                response_format="json",
            )
            parsed = self._parse(resp.content)
            return self._to_scores(parsed)
        except Exception as e:
            print(f"[LLMJudge] 评判失败，降级启发式评分: {e}")
            return self._heuristic_evaluate(output)

    def _build_prompt(self, output: Any, context: Dict, station_id: str) -> str:
        output_str = json.dumps(output, ensure_ascii=False, default=str)[:2000]
        context_str = json.dumps(context, ensure_ascii=False, default=str)[:1000]
        return (f"站点: {station_id}\n"
                f"产出内容:\n{output_str}\n\n"
                f"上下文:\n{context_str}\n\n"
                f"请按系统要求输出评分 JSON。")

    def _parse(self, content: str) -> Dict:
        try:
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            return json.loads(content.strip())
        except Exception:
            return {}

    def _to_scores(self, parsed: Dict) -> QualityScores:
        def clamp(v, default=0.0):
            try:
                return max(0.0, min(1.0, float(v)))
            except (TypeError, ValueError):
                return default

        scores = QualityScores(
            coherence=clamp(parsed.get("coherence"), 0.0),
            creativity=clamp(parsed.get("creativity"), 0.0),
            consistency=clamp(parsed.get("consistency"), 0.0),
            grammar=clamp(parsed.get("grammar"), 0.0),
            engagement=clamp(parsed.get("engagement"), 0.0),
        )
        # 若 LLM 返回了缺失/全零，降级到启发式
        if scores.average() <= 0.01:
            return self._heuristic_evaluate(None)
        return scores

    def _heuristic_evaluate(self, output: Any) -> QualityScores:
        """启发式兜底评分：基于产出内容的确定性打分（空/过短产出低分，
        结构越完整分越高），保证分数随质量真实变化且流程不卡死"""
        score = self._content_score(output)
        return QualityScores(score, score, score, score, score)

    @staticmethod
    def _content_score(output: Any) -> float:
        if output is None:
            return 0.30
        if isinstance(output, dict):
            if not output:
                return 0.30
            non_empty = sum(1 for v in output.values() if v not in (None, "", [], {}))
            if non_empty == 0:
                return 0.40
            size = len(json.dumps(output, ensure_ascii=False, default=str))
            score = 0.85 + 0.03 * min(non_empty - 1, 3)  # 结构完整性
            if size >= 200:
                score += 0.04                              # 内容充实度
            return min(score, 0.95)
        if isinstance(output, str):
            n = len(output.strip())
            if n == 0:
                return 0.30
            if n < 20:
                return 0.60
            if n < 100:
                return 0.80
            return 0.90
        return 0.70

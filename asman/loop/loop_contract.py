"""ASMAN 2.0 Loop Contract - Loop Engineering风格显式done定义"""

from typing import Dict, Any, List, Callable
from dataclasses import dataclass


@dataclass
class DoneCondition:
    name: str
    description: str
    validator: Callable[[Any], bool]
    required: bool = True


class LoopContract:
    def __init__(self, task_type: str):
        self.task_type = task_type
        self.conditions: List[DoneCondition] = []
        self._init_conditions()

    def _init_conditions(self):
        if self.task_type == "novel_creation":
            self.conditions = [
                DoneCondition("all_subs_reassembled", "所有子乘客已重组",
                              lambda ctx: ctx.get("subs_reassembled", False)),
                DoneCondition("all_gates_passed", "所有质量门已通过",
                              lambda ctx: len(ctx.get("failed_gates", [])) == 0),
                DoneCondition("all_backloops_converged", "所有回环已收敛",
                              lambda ctx: not ctx.get("active_backloops", False)),
                DoneCondition("all_outputs_ready", "所有产出物已生成",
                              lambda ctx: all(k in ctx.get("outputs", {}) for k in ["novel", "script", "videos"])),
                DoneCondition("no_pending_retries", "没有挂起的重试",
                              lambda ctx: not ctx.get("pending_retries", False)),
            ]
        elif self.task_type == "chapter_writing":
            self.conditions = [
                DoneCondition("word_count_met", "字数达标",
                              lambda ctx: ctx.get("word_count", 0) >= ctx.get("target_words", 3000)),
                DoneCondition("quality_passed", "质量通过",
                              lambda ctx: ctx.get("quality_score", 0) >= 0.85),
            ]

    def check(self, context: Dict) -> Dict[str, Any]:
        results = {}
        all_passed = True
        for condition in self.conditions:
            try:
                passed = condition.validator(context)
            except Exception:
                passed = False
            results[condition.name] = {
                "passed": passed,
                "required": condition.required,
                "description": condition.description
            }
            if condition.required and not passed:
                all_passed = False
        return {"all_passed": all_passed, "conditions": results}

    def get_pending_conditions(self, context: Dict) -> List[str]:
        result = self.check(context)
        pending = []
        for name, info in result["conditions"].items():
            if info["required"] and not info["passed"]:
                pending.append(name)
        return pending

"""ASMAN 2.0 GEPA - Genetic-Pareto Prompt Evolution"""

import random
from typing import Dict, List, Any, Optional
from .skill_library import SkillLibrary


class GEPAEvolver:
    def __init__(self, skill_library: SkillLibrary):
        self.skill_library = skill_library
        self.population_size = 5
        self.mutation_rate = 0.3

    async def evolve_skill(self, skill_id: str, execution_traces: List[Dict]) -> Optional[str]:
        if not execution_traces:
            return None
        parents = sorted(execution_traces, key=lambda x: x.get("score", 0), reverse=True)[:3]
        offspring = []
        for parent in parents:
            for _ in range(2):
                mutated = self._mutate_prompt(parent["prompt"])
                offspring.append({"prompt": mutated, "parent_score": parent["score"]})
        best = self._pareto_select(offspring)
        if best:
            new_skill_id = self.skill_library.store_skill(
                capability="evolved",
                profile="auto",
                description="Evolved from " + skill_id,
                prompt_template=best["prompt"],
                tags=["evolved", "gepa"],
                success_rate=best.get("parent_score", 0.8)
            )
            return new_skill_id
        return None

    def _mutate_prompt(self, prompt: str) -> str:
        mutations = [
            lambda p: p + " [要求:逻辑严密，前后一致]",
            lambda p: p.replace("写", "创作") if "写" in p else p + " [要求:生动描写]",
            lambda p: p + " [要求:角色性格一致]",
            lambda p: "[高质量创作要求] " + p + " [要求:情节紧凑，冲突明确]",
        ]
        mutator = random.choice(mutations)
        return mutator(prompt)

    def _pareto_select(self, candidates: List[Dict]) -> Optional[Dict]:
        if not candidates:
            return None
        return max(candidates, key=lambda x: x.get("parent_score", 0))

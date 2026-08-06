"""ASMAN 2.0 Engine - 真实LLM版"""

import asyncio
import uuid
import time
from typing import Dict, Any

from .core.models import Passenger, Ticket, Itinerary, TaskConfig, PassengerStatus
from .core.bootstrapper import Bootstrapper
from .core.convergence import ConvergenceEngine
from .state.state_layer import StateLayer
from .skill.skill_library import SkillLibrary
from .skill.skill_evolver import GEPAEvolver
from .verifier.moa_aggregator import MoAAggregator
from .loop.loop_contract import LoopContract
from .loop.three_tier_loop import ThreeTierLoop
from .profile.profile_manager import ProfileManager
from .nudge.nudge_engine import NudgeEngine
from .network import NovelSubwayNetwork, HubManager, TrainDispatcher, OCC
from .bridge.hermes_bridge import HermesBridge
from .llm.client import LLMClient


class AutoDeliverer:
    async def deliver(self, passenger: Passenger) -> Dict[str, Any]:
        outputs = {
            "novel": passenger.baggage.get("merged_W2_SLICE", {}),
            "script": passenger.baggage.get("merged_D3_SLICE", {}),
            "videos": passenger.baggage.get("video_outputs", []),
            "publish_status": passenger.baggage.get("merged_P3_SLICE", {}),
            "report": {
                "task_id": passenger.passenger_id,
                "title": passenger.ticket.config.title if passenger.ticket.config else "",
                "genre": passenger.ticket.config.genre if passenger.ticket.config else "",
                "total_stations": len(passenger.completed_stops),
                "fixes": len(passenger.fix_history),
                "skill_applied": passenger.skill_applied,
                "execution_time": time.time() - passenger.created_at,
                "status": "completed"
            }
        }
        passenger.status = PassengerStatus.COMPLETED
        return outputs


class AutonomousNovelEngine:
    def __init__(self, llm_provider: str = None, api_key: str = None, base_url: str = None):
        self.occ = OCC()
        self.bootstrapper = Bootstrapper()
        self.dispatcher = TrainDispatcher()
        self.hub_manager = HubManager()
        self.convergence = ConvergenceEngine(None, self.occ)
        self.deliverer = AutoDeliverer()
        self.network = NovelSubwayNetwork(self.occ)
        self.backloop = None
        self.running = False

        # 初始化LLM客户端（真实API）
        self.llm_client = LLMClient(
            provider=llm_provider,
            api_key=api_key,
            base_url=base_url
        )
        print(f"[Engine] LLM Provider: {self.llm_client.provider}")

        # Hermes桥接器（使用真实LLM）
        self.hermes_bridge = HermesBridge(self.llm_client)

        # 原有模块
        self.state_layer = StateLayer("asman2_state.db")
        self.skill_library = SkillLibrary("asman2_skills.db")
        self.skill_evolver = GEPAEvolver(self.skill_library)
        self.moa_verifier = MoAAggregator(num_verifiers=3)
        self.profile_manager = ProfileManager()
        self.three_tier_loop = ThreeTierLoop(self)
        self.nudge_engine = NudgeEngine(self.state_layer, self.skill_library, None)

    async def build_network(self):
        from .core.backloop import BackloopChannel
        self.backloop = BackloopChannel(self.network)
        self.network.build_default_network(self.backloop, self.hub_manager)
        self.hub_manager.network = self.network  # 注入网络引用（换乘需要）
        self.convergence.network = self.network

        for line in self.network.lines.values():
            for s in line.stations:
                s.dispatcher = self.dispatcher
                s.backloop = self.backloop
                s.hub_manager = self.hub_manager
                s.state_layer = self.state_layer
                s.skill_library = self.skill_library
                s.moa_verifier = self.moa_verifier
                s.hermes_bridge = self.hermes_bridge

        self.nudge_engine.self_healing = getattr(self.network, 'self_healing', None)

    async def run(self, user_input: str) -> str:
        if not self.network.lines:
            await self.build_network()

        config = await self.bootstrapper.bootstrap(user_input)
        itinerary = self.network.plan_itinerary(config)

        passenger = Passenger(
            passenger_id=f"NOVEL_{uuid.uuid4().hex[:8]}",
            ticket=Ticket(
                origin="S1",
                destinations=["V_END"],
                transfer_hubs=["H1", "H2", "H3", "H4", "H5"],
                config=config
            ),
            itinerary=itinerary,
            baggage={"request": config.user_input, "config": config},
            priority=5
        )

        self.occ.register_passenger(passenger)
        self.state_layer.save_passenger(passenger)
        origin = self.network.lines["L1"].stations[0]
        await origin.platform.wait(passenger)
        self.state_layer.enqueue_to_platform("S1", passenger.passenger_id, passenger.priority)

        if not self.running:
            self.running = True
            asyncio.create_task(self._autonomous_loop())
            asyncio.create_task(self.three_tier_loop.start())
            asyncio.create_task(self.nudge_engine.start())

        return passenger.passenger_id

    async def _autonomous_loop(self):
        for line in self.network.lines.values():
            asyncio.create_task(line.run(self.dispatcher, self.hub_manager, self.occ))
        asyncio.create_task(self.backloop.run())

        while self.running:
            for passenger in list(self.occ.registry.values()):
                if passenger.status == PassengerStatus.COMPLETED:
                    continue
                try:
                    converged = await self.convergence.converge(passenger)
                    if converged and passenger.status != PassengerStatus.COMPLETED:
                        result = await self.deliverer.deliver(passenger)
                        print(f"\n🎉 任务完成: {passenger.passenger_id}")
                        print(f"   标题: {passenger.ticket.config.title if passenger.ticket.config else ''}")
                        print(f"   产物: 小说 + 视频 + 发布状态")
                        exec_time = result["report"]["execution_time"]
                        print(f"   耗时: {exec_time:.1f}秒")

                        hermes_stats = self.hermes_bridge.get_execution_summary()
                        if hermes_stats:
                            print(f"   LLM调用: {hermes_stats.get('total_executions', 0)}次")
                            print(f"   总成本: ${hermes_stats.get('total_cost_usd', 0):.4f}")
                except Exception:
                    pass
            await asyncio.sleep(2)

    async def get_progress(self, task_id: str) -> Dict[str, Any]:
        passenger = self.occ.get_passenger(task_id)
        if not passenger:
            return {"error": "Task not found"}

        hermes_stats = self.hermes_bridge.get_worker_stats()

        return {
            "task_id": task_id,
            "status": passenger.status.value,
            "current_station": passenger.current_location,
            "progress_percent": passenger.itinerary.progress_percent(),
            "completed_stops": passenger.completed_stops,
            "fix_count": len(passenger.fix_history),
            "quality_scores": {k: v.average() for k, v in passenger.quality_scores.items()},
            "is_converged": await self.convergence.converge(passenger),
            "skill_stats": self.skill_library.get_skill_stats(),
            "hermes_workers": {k: {"executions": v["executions"], "success_rate": v["success_rate"], "cost": v["total_cost_usd"]} 
                              for k, v in hermes_stats.items()}
        }

    async def shutdown(self):
        self.running = False

    def get_hermes_summary(self) -> Dict:
        return self.hermes_bridge.get_execution_summary()

"""MetroEngine：通用地铁多Agent引擎

业务无关的编排核心。业务通过注入实现：
- EngineConfig（拓扑/profiles/llm/judge 配置）
- Bootstrapper（输入 → TaskConfig）
- 已注册的 Agent / Profile（registry）

运行循环由多条后台任务驱动：
线路列车调度、回环通道、三层控制循环、自愈体检、后台复盘。
"""

import asyncio
import uuid
import time
from typing import Dict, Any, Optional

from .core.models import Passenger, Ticket, TaskConfig, PassengerStatus
from .core.bootstrapper import Bootstrapper, DefaultBootstrapper
from .core.convergence import ConvergenceEngine
from .core.self_healing import SelfHealingScheduler
from .state.state_layer import StateLayer
from .skill.skill_library import SkillLibrary
from .skill.skill_evolver import GEPAEvolver
from .verifier.moa_aggregator import MoAAggregator
from .loop.three_tier_loop import ThreeTierLoop
from .nudge.nudge_engine import NudgeEngine
from .core.network import MetroNetwork, HubManager, TrainDispatcher, OCC, NetworkConfig
from .bridge.hermes_bridge import HermesBridge
from .bridge.hermes_config import load_profiles
from .llm.client import LLMClient
from .judge.judge import LLMJudge
from .registry import register_profile
from .runtime.config import EngineConfig
from .runtime.logging import get_logger, setup_logging
from .runtime.metrics import Metrics

logger = get_logger("asman.engine")


class AutoDeliverer:
    """自动交付：收敛后打包乘客行李与执行报告"""

    def __init__(self, metrics: Optional[Metrics] = None):
        self.metrics = metrics

    async def deliver(self, passenger: Passenger) -> Dict[str, Any]:
        outputs = {
            "task_id": passenger.passenger_id,
            "title": passenger.ticket.config.title if passenger.ticket.config else "",
            "status": "completed",
            "total_stations": len(passenger.completed_stops),
            "fixes": len(passenger.fix_history),
            "execution_time": time.time() - passenger.created_at,
            "baggage": passenger.baggage,  # 业务产物全在行李里
        }
        passenger.status = PassengerStatus.COMPLETED
        if self.metrics:
            self.metrics.incr("tasks_completed")
        return outputs


class MetroEngine:
    def __init__(self, config: Optional[EngineConfig] = None,
                 bootstrapper: Optional[Bootstrapper] = None):
        setup_logging()
        self.config = config or EngineConfig()
        self.bootstrapper = bootstrapper or DefaultBootstrapper()
        self.metrics = Metrics()

        self.occ = OCC()
        self.dispatcher = TrainDispatcher()
        self.hub_manager = HubManager()
        self.network = MetroNetwork(self.occ)
        self.backloop = None
        self.running = False
        self.network_config: Optional[NetworkConfig] = None

        # LLM 客户端
        self.llm_client = LLMClient(
            provider=self.config.llm.provider,
            api_key=self.config.llm.api_key,
            base_url=self.config.llm.base_url,
        )

        # Judge（独立或复用主 LLM）
        jc = self.config.judge
        self.judge: Optional[LLMJudge] = None
        if jc.enabled:
            judge_llm = LLMClient(
                provider=jc.provider or self.config.llm.provider,
                api_key=jc.api_key or self.config.llm.api_key,
                base_url=jc.base_url or self.config.llm.base_url,
            )
            self.judge = LLMJudge(judge_llm, model=jc.model,
                                  temperature=jc.temperature, max_tokens=jc.max_tokens)

        # Hermes 桥接 + 各模块
        self.hermes_bridge = HermesBridge(self.llm_client)
        self.hermes_bridge.metrics = self.metrics
        self.state_layer = StateLayer(self.config.state_db)
        self.skill_library = SkillLibrary(self.config.skill_db)
        self.skill_evolver = GEPAEvolver(self.skill_library)
        self.moa_verifier = MoAAggregator(judge=self.judge, num_verifiers=1)
        self.three_tier_loop = ThreeTierLoop(self)
        self.convergence = ConvergenceEngine(None, self.occ)
        self.deliverer = AutoDeliverer(self.metrics)

        # 自愈 + 复盘（真正启动）
        self.self_healing = SelfHealingScheduler(self.network, self.occ, self.dispatcher)
        self.nudge_engine = NudgeEngine(self.state_layer, self.skill_library,
                                        self.self_healing, self.network)

    async def build_network(self):
        from .core.backloop import BackloopChannel

        self.backloop = BackloopChannel(self.network)

        # 1. 加载 Profile 到注册表
        for station_id, prof in load_profiles(self.config.profiles).items():
            register_profile(station_id, prof)

        # 2. 解析拓扑配置并构建网络
        self.network_config = NetworkConfig(**self.config.network)
        self.network.build_from_config(self.network_config, self.backloop,
                                       self.hub_manager, self.dispatcher)
        self.hub_manager.network = self.network
        self.convergence.network = self.network
        self.convergence.required_outputs = self._infer_required_outputs(self.network_config)

        # 3. 注入站点依赖
        for line in self.network.lines.values():
            for s in line.stations:
                s.dispatcher = self.dispatcher
                s.backloop = self.backloop
                s.hub_manager = self.hub_manager
                s.state_layer = self.state_layer
                s.skill_library = self.skill_library
                s.moa_verifier = self.moa_verifier
                s.hermes_bridge = self.hermes_bridge
                s.metrics = self.metrics

    def _infer_required_outputs(self, net_cfg: NetworkConfig) -> list:
        """收敛所需的产物 key：所有切片站的 merged_{station_id}"""
        outputs = []
        for line in net_cfg.lines:
            for sc in line.stations:
                if sc.slice:
                    outputs.append(f"merged_{sc.id}")
        return outputs

    async def run(self, user_input: str) -> str:
        if not self.network.lines:
            await self.build_network()

        config = await self.bootstrapper.bootstrap(user_input)
        itinerary = self.network.plan_itinerary(self.network_config)
        origin, destinations, transfer_hubs = self._derive_ticket(itinerary)

        passenger = Passenger(
            passenger_id=f"TASK_{uuid.uuid4().hex[:8]}",
            ticket=Ticket(
                origin=origin,
                destinations=destinations,
                transfer_hubs=transfer_hubs,
                config=config,
            ),
            itinerary=itinerary,
            baggage={"request": user_input, "config": config},
            priority=5,
        )

        self.occ.register_passenger(passenger)
        self.state_layer.save_passenger(passenger)
        start = self.network.lines[itinerary.segments[0].line_id].stations[0]
        await start.platform.wait(passenger)
        self.state_layer.enqueue_to_platform(start.station_id, passenger.passenger_id,
                                             passenger.priority)
        self.metrics.incr("tasks_created")

        if not self.running:
            self.running = True
            self._start_background_tasks()

        logger.info("任务已创建: %s", passenger.passenger_id)
        return passenger.passenger_id

    def _derive_ticket(self, itinerary):
        segments = itinerary.segments
        origin = segments[0].board_station if segments else ""
        last = segments[-1].alight_stations if segments else []
        destinations = [last[-1]] if last else []
        transfer_hubs = [s.transfer_out_hub for s in segments[:-1] if s.transfer_out_hub]
        return origin, destinations, transfer_hubs

    def _start_background_tasks(self):
        for line in self.network.lines.values():
            asyncio.create_task(line.run(self.dispatcher, self.hub_manager, self.occ))
        asyncio.create_task(self.backloop.run())
        asyncio.create_task(self.three_tier_loop.start())
        asyncio.create_task(self.self_healing.health_check_loop())
        asyncio.create_task(self.nudge_engine.start())

    async def recover(self) -> int:
        """从 SQLite 恢复未完成的乘客并重新入站台（崩溃恢复）

        启动时调用，返回恢复的乘客数。恢复会重建 Itinerary（从配置）、
        Ticket（config 从 baggage 恢复），并放回 current_location 站台。
        """
        if not self.network.lines:
            await self.build_network()

        rows = self.state_layer.load_active_passengers_full()
        recovered = 0
        for row in rows:
            try:
                baggage = row.get("baggage") or {}
                config = baggage.get("config")
                itinerary = self.network.plan_itinerary(self.network_config)
                itinerary.current_segment_idx = row.get("segment_idx") or 0
                origin, destinations, transfer_hubs = self._derive_ticket(itinerary)

                passenger = Passenger(
                    passenger_id=row["passenger_id"],
                    ticket=Ticket(origin=origin, destinations=destinations,
                                  transfer_hubs=transfer_hubs, config=config),
                    itinerary=itinerary,
                    baggage=baggage,
                    priority=row.get("priority", 5),
                    parent_id=row.get("parent_id") or None,
                )
                passenger.completed_stops = row.get("completed_stops") or []
                try:
                    passenger.status = PassengerStatus(row.get("status", "waiting"))
                except ValueError:
                    passenger.status = PassengerStatus.WAITING
                passenger.current_location = row.get("current_location") or ""

                self.occ.register_passenger(passenger)
                station = self.network.get_station(passenger.current_location)
                if station:
                    await station.platform.wait(passenger)
                recovered += 1
            except Exception as e:
                logger.warning("恢复乘客 %s 失败: %s", row.get("passenger_id"), e)

        if recovered:
            logger.info("已从 SQLite 恢复 %d 个未完成乘客", recovered)
        return recovered

    async def get_progress(self, task_id: str) -> Dict[str, Any]:
        passenger = self.occ.get_passenger(task_id)
        if not passenger:
            return {"error": "Task not found"}

        hermes_stats = self.hermes_bridge.get_worker_stats()

        progress = (100.0 if passenger.status == PassengerStatus.COMPLETED
                    else passenger.itinerary.progress_percent())

        return {
            "task_id": task_id,
            "status": passenger.status.value,
            "current_station": passenger.current_location,
            "progress_percent": progress,
            "completed_stops": passenger.completed_stops,
            "fix_count": len(passenger.fix_history),
            "quality_scores": {k: v.average() for k, v in passenger.quality_scores.items()},
            "is_converged": await self.convergence.converge(passenger),
            "skill_stats": self.skill_library.get_skill_stats(),
            "hermes_workers": {
                k: {"executions": v["executions"], "success_rate": v["success_rate"],
                    "cost": v["total_cost_usd"]}
                for k, v in hermes_stats.items()
            },
        }

    async def shutdown(self):
        logger.info("开始优雅关闭...")
        self.running = False
        self.three_tier_loop.stop()
        self.self_healing.running = False
        self.nudge_engine.running = False
        if self.backloop:
            self.backloop.running = False
        for line in self.network.lines.values():
            line.running = False
        # 落盘：保存所有乘客最终状态
        for p in self.occ.registry.values():
            self.state_layer.save_passenger(p)
        self.state_layer.close()
        self.skill_library.close()
        logger.info("已关闭（状态已落盘）")

    def get_metrics(self) -> Dict:
        return self.metrics.snapshot()

    def get_hermes_summary(self) -> Dict:
        return self.hermes_bridge.get_execution_summary()

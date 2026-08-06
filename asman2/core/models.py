"""ASMAN 2.0 Core Models - 融合版"""

import asyncio
import uuid
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
from datetime import datetime


class PassengerStatus(Enum):
    WAITING = "waiting"
    ONBOARD = "onboard"
    PROCESSING = "processing"
    SPLIT_WAITING = "split_waiting"
    TRANSFERING = "transfering"
    BACKLOOPING = "backlooping"
    COMPLETED = "completed"
    FAILED = "failed"

class TrainStatus(Enum):
    IDLE = "idle"
    BOARDING = "boarding"
    RUNNING = "running"
    ARRIVED = "arrived"

class GateResult(Enum):
    PASS = "pass"
    RETRY = "retry"
    BACKLOOP = "backloop"

@dataclass
class TaskConfig:
    title: str = ""
    genre: str = ""
    chapters: int = 3
    word_count_per_chapter: int = 1500
    target_platforms: List[str] = field(default_factory=list)
    style: str = ""
    need_video: bool = True
    quality_threshold: float = 0.85
    max_retry: int = 3
    timeout_per_task: int = 300
    user_input: str = ""

@dataclass
class Ticket:
    origin: str
    destinations: List[str]
    transfer_hubs: List[str]
    max_stops: int = 50
    expires_at: Optional[datetime] = None
    config: Optional[TaskConfig] = None

    def derive_for_slice(self, slice_data: Dict) -> "Ticket":
        return Ticket(
            origin=self.origin,
            destinations=self.destinations,
            transfer_hubs=self.transfer_hubs,
            max_stops=self.max_stops,
            expires_at=self.expires_at,
            config=self.config
        )

@dataclass
class Segment:
    line_id: str
    board_station: str
    alight_stations: List[str]
    transfer_out_hub: Optional[str] = None

@dataclass
class Itinerary:
    segments: List[Segment]
    current_segment_idx: int = 0

    def current_segment(self) -> Optional[Segment]:
        if self.current_segment_idx < len(self.segments):
            return self.segments[self.current_segment_idx]
        return None

    def next_segment(self) -> Optional[Segment]:
        if self.current_segment_idx + 1 < len(self.segments):
            return self.segments[self.current_segment_idx + 1]
        return None

    def progress_percent(self) -> float:
        if not self.segments:
            return 100.0
        return (self.current_segment_idx / len(self.segments)) * 100

@dataclass
class QualityScores:
    coherence: float = 0.0
    creativity: float = 0.0
    consistency: float = 0.0
    grammar: float = 0.0
    engagement: float = 0.0

    def average(self) -> float:
        return sum([self.coherence, self.creativity, self.consistency, self.grammar, self.engagement]) / 5

@dataclass
class FixHistory:
    from_station: str
    to_station: str
    reason: str
    timestamp: float = field(default_factory=time.time)

class Passenger:
    def __init__(self, passenger_id: str, ticket: Ticket, itinerary: Itinerary,
                 baggage: Optional[Dict[str, Any]] = None, priority: int = 5,
                 parent_id: Optional[str] = None, slice_id: Optional[str] = None):
        self.passenger_id = passenger_id
        self.ticket = ticket
        self.itinerary = itinerary
        self.baggage: Dict[str, Any] = baggage or {}
        self.priority = priority
        self.status = PassengerStatus.WAITING
        self.current_location = ""
        self.completed_stops: List[str] = []
        self.created_at = time.time()
        self.parent_id = parent_id
        self.slice_id = slice_id
        self.retry_count: Dict[str, int] = {}
        self.fix_history: List[FixHistory] = []
        self.quality_scores: Dict[str, QualityScores] = {}
        self.failed_gates: List[str] = []
        self.slice_station: Optional[str] = None
        self.is_sub = parent_id is not None
        self.checkpoint_id: Optional[str] = None
        self.skill_applied: Optional[str] = None

    def should_alight_at(self, station_id: str) -> bool:
        seg = self.itinerary.current_segment()
        if not seg:
            return False
        return station_id in seg.alight_stations and station_id not in self.completed_stops

    def has_more_stops_in_segment(self) -> bool:
        seg = self.itinerary.current_segment()
        if not seg:
            return False
        for s in seg.alight_stations:
            if s not in self.completed_stops:
                return True
        return False

    def next_destination(self) -> Optional[str]:
        seg = self.itinerary.current_segment()
        if not seg:
            return None
        for s in seg.alight_stations:
            if s not in self.completed_stops:
                return s
        return None

    def get_retry_count(self, station_id: str) -> int:
        return self.retry_count.get(station_id, 0)

    def increment_retry(self, station_id: str):
        self.retry_count[station_id] = self.retry_count.get(station_id, 0) + 1

    def to_dict(self) -> Dict:
        return {
            "passenger_id": self.passenger_id,
            "status": self.status.value,
            "current_location": self.current_location,
            "progress": self.itinerary.progress_percent(),
            "completed_stops": self.completed_stops,
            "is_sub": self.is_sub,
            "parent_id": self.parent_id,
            "fix_history_count": len(self.fix_history),
            "baggage_keys": list(self.baggage.keys())
        }

class SubPassenger(Passenger):
    def __init__(self, passenger_id: str, parent_id: str, **kwargs):
        super().__init__(passenger_id=passenger_id, parent_id=parent_id, **kwargs)
        self.slice_id = passenger_id.split("#")[1] if "#" in passenger_id else ""

class FixPassenger(Passenger):
    def __init__(self, original_id: str, target_station: str, error_context: Dict, **kwargs):
        super().__init__(**kwargs)
        self.original_id = original_id
        self.target_station = target_station
        self.error_context = error_context
        self.is_fix = True

@dataclass
class Train:
    train_id: str
    line_id: str
    capacity: int = 10
    passengers: List[Passenger] = field(default_factory=list)
    current_station: str = ""
    route_stops: List[str] = field(default_factory=list)
    status: TrainStatus = TrainStatus.IDLE

    def compute_route(self, line) -> List[str]:
        stops = set()
        for p in self.passengers:
            seg = p.itinerary.current_segment()
            if seg and seg.line_id == self.line_id:
                for s in seg.alight_stations:
                    if s in line.station_map:
                        stops.add(s)
        return [s.station_id for s in line.stations if s.station_id in stops]

    def has_passengers(self) -> bool:
        return len(self.passengers) > 0
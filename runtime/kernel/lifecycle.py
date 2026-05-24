"""
AVAListener — Runtime State Machine
===================================
Explicit runtime states used for debugging, recovery, and SDK integration.
"""

from __future__ import annotations
from enum import Enum
import logging
from utils.logger import get_logger

log = get_logger("state_machine")


class RuntimeState(str, Enum):
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    SPEECH_DETECTED = "SPEECH_DETECTED"
    CANDIDATE_TRACKING = "CANDIDATE_TRACKING"
    WAKE_CONFIRMED = "WAKE_CONFIRMED"
    COOLDOWN = "COOLDOWN"
    RECOVERING = "RECOVERING"
    ERROR = "ERROR"

class SubsystemState(str, Enum):
    OFFLINE = "OFFLINE"
    INITIALIZING = "INITIALIZING"
    READY = "READY"
    ACTIVE = "ACTIVE"
    FAULTED = "FAULTED"
    RECOVERING = "RECOVERING"

VALID_SUBSYSTEM_TRANSITIONS = {
    SubsystemState.OFFLINE: {SubsystemState.INITIALIZING},
    SubsystemState.INITIALIZING: {SubsystemState.READY, SubsystemState.FAULTED},
    SubsystemState.READY: {SubsystemState.ACTIVE, SubsystemState.OFFLINE},
    SubsystemState.ACTIVE: {SubsystemState.READY, SubsystemState.FAULTED},
    SubsystemState.FAULTED: {SubsystemState.RECOVERING, SubsystemState.OFFLINE},
    SubsystemState.RECOVERING: {SubsystemState.ACTIVE, SubsystemState.FAULTED}
}

class SubsystemLifecycle:
    def __init__(self, name: str):
        self.name = name
        self.state = SubsystemState.OFFLINE
        
    def transition(self, target: SubsystemState, detail: str = "") -> SubsystemState:
        prev = self.state
        if target != prev and target not in VALID_SUBSYSTEM_TRANSITIONS[prev]:
            raise ValueError(f"Illegal subsystem transition for {self.name}: {prev.value} \u2192 {target.value}")
            
        self.state = target
        if self.state != prev:
            log.debug("[SUBSYSTEM] %s: %s \u2192 %s %s", self.name, prev.value, self.state.value, detail)
        return self.state

    def shutdown(self) -> None:
        """Safely transition to OFFLINE from any state following invariants."""
        if self.state == SubsystemState.OFFLINE:
            return
        if self.state == SubsystemState.INITIALIZING:
            self.transition(SubsystemState.READY)
        elif self.state == SubsystemState.ACTIVE:
            self.transition(SubsystemState.READY)
        elif self.state == SubsystemState.RECOVERING:
            self.transition(SubsystemState.FAULTED)
            
        if self.state in (SubsystemState.READY, SubsystemState.FAULTED):
            self.transition(SubsystemState.OFFLINE)
            
    def recover(self, detail: str = "") -> None:
        """Safely transition to RECOVERING from any state following invariants."""
        if self.state == SubsystemState.ACTIVE:
            self.transition(SubsystemState.FAULTED, detail)
        if self.state == SubsystemState.FAULTED:
            self.transition(SubsystemState.RECOVERING, detail)


class RuntimeStateMachine:
    def __init__(self) -> None:
        self.state = RuntimeState.IDLE

    def transition(self, event: str, detail: str = "") -> RuntimeState:
        prev = self.state
        transition_map = {
            "start": RuntimeState.LISTENING,
            "speech_start": RuntimeState.SPEECH_DETECTED,
            "candidate_started": RuntimeState.CANDIDATE_TRACKING,
            "candidate_updated": RuntimeState.CANDIDATE_TRACKING,
            "candidate_confirmed": RuntimeState.WAKE_CONFIRMED,
            "candidate_dropped": RuntimeState.LISTENING,
            "cooldown": RuntimeState.COOLDOWN,
            "recovery": RuntimeState.RECOVERING,
            "ready": RuntimeState.LISTENING,
            "error": RuntimeState.ERROR,
            "reset": RuntimeState.LISTENING,
        }

        self.state = transition_map.get(event, self.state)
        if self.state != prev:
            if self.state in (RuntimeState.WAKE_CONFIRMED, RuntimeState.COOLDOWN):
                log.info("FSM: %s \u2192 %s %s", prev.value, self.state.value, detail)
            else:
                log.debug("FSM: %s \u2192 %s %s", prev.value, self.state.value, detail)
        else:
            log.debug("[STATE] remain %s %s", self.state.value, detail)
        return self.state

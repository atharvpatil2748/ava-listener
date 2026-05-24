import sys
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from runtime.kernel.lifecycle import SubsystemLifecycle, SubsystemState, VALID_SUBSYSTEM_TRANSITIONS

class _pytest_mock:
    class raises:
        def __init__(self, exc_type):
            self.exc_type = exc_type
        def __enter__(self):
            pass
        def __exit__(self, exc_type, exc_val, exc_tb):
            if exc_type is None:
                raise AssertionError(f"Expected exception {self.exc_type.__name__} not raised")
            if not issubclass(exc_type, self.exc_type):
                return False
            return True

pytest = _pytest_mock()


def test_valid_startup_sequence():
    fsm = SubsystemLifecycle("Test")
    assert fsm.state == SubsystemState.OFFLINE
    fsm.transition(SubsystemState.INITIALIZING)
    fsm.transition(SubsystemState.READY)
    fsm.transition(SubsystemState.ACTIVE)
    assert fsm.state == SubsystemState.ACTIVE

def test_recovery_sequence():
    fsm = SubsystemLifecycle("Test")
    fsm.transition(SubsystemState.INITIALIZING)
    fsm.transition(SubsystemState.READY)
    fsm.transition(SubsystemState.ACTIVE)
    
    fsm.recover()
    assert fsm.state == SubsystemState.RECOVERING
    fsm.transition(SubsystemState.ACTIVE)
    assert fsm.state == SubsystemState.ACTIVE

def test_shutdown_sequence():
    fsm = SubsystemLifecycle("Test")
    fsm.transition(SubsystemState.INITIALIZING)
    fsm.transition(SubsystemState.READY)
    fsm.transition(SubsystemState.ACTIVE)
    
    fsm.shutdown()
    assert fsm.state == SubsystemState.OFFLINE

def test_illegal_transitions():
    fsm = SubsystemLifecycle("Test")
    
    # OFFLINE -> ACTIVE is illegal
    with pytest.raises(ValueError):
        fsm.transition(SubsystemState.ACTIVE)
        
    fsm.transition(SubsystemState.INITIALIZING)
    fsm.transition(SubsystemState.READY)
    fsm.transition(SubsystemState.ACTIVE)
    
    # ACTIVE -> INITIALIZING is illegal
    with pytest.raises(ValueError):
        fsm.transition(SubsystemState.INITIALIZING)
        
    fsm.transition(SubsystemState.READY)
    # READY -> RECOVERING is illegal
    with pytest.raises(ValueError):
        fsm.transition(SubsystemState.RECOVERING)

def test_shutdown_helper_from_any_state():
    # From OFFLINE
    fsm = SubsystemLifecycle("Test")
    fsm.shutdown()
    assert fsm.state == SubsystemState.OFFLINE
    
    # From INITIALIZING
    fsm = SubsystemLifecycle("Test")
    fsm.transition(SubsystemState.INITIALIZING)
    fsm.shutdown()
    assert fsm.state == SubsystemState.OFFLINE
    
    # From RECOVERING
    fsm = SubsystemLifecycle("Test")
    fsm.transition(SubsystemState.INITIALIZING)
    fsm.transition(SubsystemState.READY)
    fsm.transition(SubsystemState.ACTIVE)
    fsm.recover()
    fsm.shutdown()
    assert fsm.state == SubsystemState.OFFLINE

def test_valid_transitions_map_matches_contract():
    assert VALID_SUBSYSTEM_TRANSITIONS[SubsystemState.OFFLINE] == {SubsystemState.INITIALIZING}
    assert VALID_SUBSYSTEM_TRANSITIONS[SubsystemState.INITIALIZING] == {SubsystemState.READY, SubsystemState.FAULTED}
    assert VALID_SUBSYSTEM_TRANSITIONS[SubsystemState.READY] == {SubsystemState.ACTIVE, SubsystemState.OFFLINE}
    assert VALID_SUBSYSTEM_TRANSITIONS[SubsystemState.ACTIVE] == {SubsystemState.READY, SubsystemState.FAULTED}
    assert VALID_SUBSYSTEM_TRANSITIONS[SubsystemState.FAULTED] == {SubsystemState.RECOVERING, SubsystemState.OFFLINE}
    assert VALID_SUBSYSTEM_TRANSITIONS[SubsystemState.RECOVERING] == {SubsystemState.ACTIVE, SubsystemState.FAULTED}

if __name__ == "__main__":
    print("Running transition invariants tests...")
    

    test_valid_startup_sequence()
    test_recovery_sequence()
    test_shutdown_sequence()
    test_illegal_transitions()
    test_shutdown_helper_from_any_state()
    test_valid_transitions_map_matches_contract()
    
    print("All transition invariants tests PASS")

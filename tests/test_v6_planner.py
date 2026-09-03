import pytest
from backend.services.selection.planner import ClipPlanner

class DummyMapping:
    def __init__(self, start, end):
        self.start_timestamp = start
        self.end_timestamp = end

class DummySource:
    def __init__(self, duration):
        self.source_duration = duration

def test_valid_timestamps():
    planner = ClipPlanner()
    mapping = DummyMapping(10.0, 25.0)
    source = DummySource(100.0)
    
    s, e, c, r = planner.plan_clip(mapping, source)
    assert s == 10.0
    assert e == 25.0
    assert c == "HUMAN_PROVIDED"

def test_missing_timestamps():
    planner = ClipPlanner()
    mapping = DummyMapping(None, None)
    source = DummySource(100.0)
    
    s, e, c, r = planner.plan_clip(mapping, source)
    assert s is None
    assert e is None
    assert c == "UNKNOWN"

def test_invalid_ranges():
    planner = ClipPlanner()
    source = DummySource(100.0)
    
    # Negative
    s, e, c, r = planner.plan_clip(DummyMapping(-5.0, 10.0), source)
    assert c == "UNKNOWN"
    
    # End <= Start
    s, e, c, r = planner.plan_clip(DummyMapping(10.0, 5.0), source)
    assert c == "UNKNOWN"
    
    # Below Min (2.0)
    s, e, c, r = planner.plan_clip(DummyMapping(10.0, 11.0), source)
    assert c == "UNKNOWN"
    
    # Above Max (60.0)
    s, e, c, r = planner.plan_clip(DummyMapping(10.0, 80.0), source)
    assert c == "UNKNOWN"
    
    # Exceeds source duration
    s, e, c, r = planner.plan_clip(DummyMapping(90.0, 110.0), source)
    assert c == "UNKNOWN"

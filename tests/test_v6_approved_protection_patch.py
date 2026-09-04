"""
V6 corrective patch regression suite.

Covers:
  - The new invariant: automated selection never overwrites a mapping
    whose selection_status is APPROVED (score, reason, confidence,
    status, and clip-plan timestamps all stay untouched).
  - That REJECTED remains fully system-writable (documented as
    unprotected technical debt -- see docs/phase-reports/v6.md).
  - That ordinary (non-APPROVED) selection behavior is unchanged:
    scoring, ranking, confidence bucketing, AUTO_SELECTED/NEEDS_REVIEW/
    REJECTED assignment, and clip planning.
  - Idempotency: running the selector twice with no state change
    produces an identical result and does not create duplicate rows.
  - "Concurrent" execution: two selector instances against the same
    session/intent cannot together clobber an APPROVED mapping.

This suite uses an isolated in-memory SQLite database per test (via the
real SQLAlchemy models, not mocks) so it exercises the actual ORM read/
write paths the selector runs against in production.
"""
import datetime
import json
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database.db import Base
from backend.models.channel import Channel
from backend.models.project import Project
from backend.models.episode import Episode
from backend.models.scene import Scene
from backend.models.narration_segment import NarrationSegment
from backend.models.visual_intent import VisualIntent
from backend.models.source_asset import SourceAsset
from backend.models.asset_mapping import AssetMapping
from backend.models.enums import AssetState, SelectionStatus, CopyrightStatus
from backend.services.selection.selector import FootageSelector

PASS = 0
FAIL = 0
FAILURES = []


def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS: {name}")
    else:
        FAIL += 1
        FAILURES.append(name + (f" -- {detail}" if detail else ""))
        print(f"  FAIL: {name} {detail}")


def make_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()


def make_intent(db, preferred_channels=None, preferred_year=None, description="No Man's Sky official gameplay reveal"):
    channel = Channel(name="TestChannel")
    db.add(channel)
    db.commit()
    project = Project(channel_id=channel.id, name="TestProject")
    db.add(project)
    db.commit()
    episode = Episode(project_id=project.id, name="TestEpisode")
    db.add(episode)
    db.commit()
    scene = Scene(episode_id=episode.id, order_index=1, title="TestScene")
    db.add(scene)
    db.commit()
    seg = NarrationSegment(scene_id=scene.id, order_index=1, text="Test narration")
    db.add(seg)
    db.commit()
    intent = VisualIntent(
        narration_segment_id=seg.id,
        description=description,
        preferred_content_types=json.dumps(["gameplay"]),
        avoid_content_types=json.dumps(["reaction"]),
        preferred_channels=json.dumps(preferred_channels or ["HelloGamesTube"]),
        preferred_year=preferred_year,
    )
    db.add(intent)
    db.commit()
    return intent


def make_source(db, url, title, channel="HelloGamesTube", duration=200.0, is_short=False, published_year=2016):
    src = SourceAsset(
        source_url=url,
        source_platform="youtube",
        source_channel=channel,
        title=title,
        description=title,
        source_duration=duration,
        is_short=is_short,
        published_date=datetime.datetime(published_year, 1, 1, tzinfo=datetime.timezone.utc),
        copyright_status=CopyrightStatus.OFFICIAL_PUBLIC,
    )
    db.add(src)
    db.commit()
    return src


def make_mapping(db, intent, source, relevance_score=90.0, start=10.0, end=25.0):
    m = AssetMapping(
        visual_intent_id=intent.id,
        source_asset_id=source.id,
        state=AssetState.CANDIDATE,
        relevance_score=relevance_score,
        start_timestamp=start,
        end_timestamp=end,
    )
    db.add(m)
    db.commit()
    return m


# ---------------------------------------------------------------------
# Test 1: APPROVED mapping remains APPROVED after selection rerun.
# Test 2-5 bundled: score / reason / confidence / timestamps retained.
# ---------------------------------------------------------------------
def test_approved_is_immutable_across_rerun():
    print("\n[1-5] APPROVED mapping survives selection rerun unchanged")
    db = make_session()
    intent = make_intent(db)
    src = make_source(db, "https://youtube.com/watch?v=aaa", "No Man's Sky official gameplay")
    m = make_mapping(db, intent, src)

    selector = FootageSelector(db)
    selector.select_best_for_intent(intent.id)
    db.refresh(m)

    # Simulate a human explicitly approving this mapping, with known values.
    m.selection_status = SelectionStatus.APPROVED
    m.selection_score = 77.7
    m.selection_reason = json.dumps({"human": "approved this one deliberately"})
    m.confidence_level = "MEDIUM"
    m.start_timestamp = 12.5
    m.end_timestamp = 27.5
    m.timestamp_confidence = "HUMAN_PROVIDED"
    m.timestamp_reason = "Manually adjusted by editor"
    db.commit()

    snapshot = dict(
        status=m.selection_status,
        score=m.selection_score,
        reason=m.selection_reason,
        confidence=m.confidence_level,
        start=m.start_timestamp,
        end=m.end_timestamp,
        t_conf=m.timestamp_confidence,
        t_reason=m.timestamp_reason,
    )

    # Rerun selection.
    selector.select_best_for_intent(intent.id)
    db.refresh(m)

    check("1. status stays APPROVED", m.selection_status == SelectionStatus.APPROVED, m.selection_status)
    check("2. selection_score retained", m.selection_score == snapshot["score"], m.selection_score)
    check("3. selection_reason retained", m.selection_reason == snapshot["reason"], m.selection_reason)
    check("4. confidence_level retained", m.confidence_level == snapshot["confidence"], m.confidence_level)
    check("5. timestamps retained",
          (m.start_timestamp, m.end_timestamp, m.timestamp_confidence, m.timestamp_reason) ==
          (snapshot["start"], snapshot["end"], snapshot["t_conf"], snapshot["t_reason"]),
          (m.start_timestamp, m.end_timestamp, m.timestamp_confidence, m.timestamp_reason))
    db.close()


# ---------------------------------------------------------------------
# Test 6: adding a new higher-scoring candidate does not demote APPROVED.
# ---------------------------------------------------------------------
def test_new_higher_scoring_candidate_does_not_demote_approved():
    print("\n[6] New higher-scoring candidate does not demote APPROVED")
    db = make_session()
    intent = make_intent(db)
    src1 = make_source(db, "https://youtube.com/watch?v=bbb", "No Man's Sky official gameplay", channel="HelloGamesTube")
    m1 = make_mapping(db, intent, src1, relevance_score=70.0)

    selector = FootageSelector(db)
    selector.select_best_for_intent(intent.id)
    db.refresh(m1)

    m1.selection_status = SelectionStatus.APPROVED
    db.commit()
    approved_score_before = m1.selection_score

    # Add a strictly better candidate (higher relevance, official channel bonus, etc.)
    src2 = make_source(db, "https://youtube.com/watch?v=ccc", "No Man's Sky official gameplay trailer", channel="HelloGamesTube")
    make_mapping(db, intent, src2, relevance_score=100.0)

    best = selector.select_best_for_intent(intent.id)
    db.refresh(m1)

    check("6a. APPROVED mapping status unchanged despite better candidate",
          m1.selection_status == SelectionStatus.APPROVED, m1.selection_status)
    check("6b. APPROVED mapping score unchanged despite better candidate",
          m1.selection_score == approved_score_before, m1.selection_score)
    check("6c. selector still reports the new candidate as its own 'best' pick",
          best is not None and best.source_asset_id == src2.id, best)
    db.close()


# ---------------------------------------------------------------------
# Test 7: repeated selector execution cannot overwrite APPROVED.
# ---------------------------------------------------------------------
def test_repeated_execution_cannot_overwrite_approved():
    print("\n[7] Repeated selector execution (5x) cannot overwrite APPROVED")
    db = make_session()
    intent = make_intent(db)
    src = make_source(db, "https://youtube.com/watch?v=ddd", "No Man's Sky official gameplay")
    m = make_mapping(db, intent, src)
    selector = FootageSelector(db)
    selector.select_best_for_intent(intent.id)
    db.refresh(m)
    m.selection_status = SelectionStatus.APPROVED
    m.selection_score = 55.5
    db.commit()

    for _ in range(5):
        selector.select_best_for_intent(intent.id)
    db.refresh(m)

    check("7. status still APPROVED after 5 reruns", m.selection_status == SelectionStatus.APPROVED)
    check("7b. score still 55.5 after 5 reruns", m.selection_score == 55.5, m.selection_score)
    db.close()


# ---------------------------------------------------------------------
# Test 8: concurrent selector execution cannot overwrite APPROVED.
# Simulated with two independent selector/session instances interleaving
# calls against the same underlying database.
# ---------------------------------------------------------------------
def test_concurrent_execution_cannot_overwrite_approved():
    print("\n[8] 'Concurrent' selector execution cannot overwrite APPROVED")
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    db_setup = SessionLocal()
    intent = make_intent(db_setup)
    src = make_source(db_setup, "https://youtube.com/watch?v=eee", "No Man's Sky official gameplay")
    m_setup = make_mapping(db_setup, intent, src)
    FootageSelector(db_setup).select_best_for_intent(intent.id)
    db_setup.refresh(m_setup)
    m_setup.selection_status = SelectionStatus.APPROVED
    m_setup.selection_score = 66.6
    db_setup.commit()
    intent_id = intent.id
    db_setup.close()

    # Two independent "workers", each with their own session, interleaving
    # selection runs against the same intent.
    db_a = SessionLocal()
    db_b = SessionLocal()
    selector_a = FootageSelector(db_a)
    selector_b = FootageSelector(db_b)

    for _ in range(3):
        selector_a.select_best_for_intent(intent_id)
        selector_b.select_best_for_intent(intent_id)

    db_check = SessionLocal()
    m_check = db_check.query(AssetMapping).filter(AssetMapping.visual_intent_id == intent_id).first()
    check("8. status still APPROVED after interleaved concurrent runs",
          m_check.selection_status == SelectionStatus.APPROVED, m_check.selection_status)
    check("8b. score still 66.6 after interleaved concurrent runs",
          m_check.selection_score == 66.6, m_check.selection_score)
    db_a.close()
    db_b.close()
    db_check.close()


# ---------------------------------------------------------------------
# Test 9: selector still correctly updates non-protected statuses.
# ---------------------------------------------------------------------
def test_non_protected_statuses_still_update_normally():
    print("\n[9] Non-APPROVED mappings still score/rank/status normally")
    db = make_session()
    intent = make_intent(db, preferred_channels=["HelloGamesTube"])

    src_official = make_source(db, "https://youtube.com/watch?v=fff",
                                "No Man's Sky official gameplay trailer",
                                channel="HelloGamesTube", published_year=2016)
    m_official = make_mapping(db, intent, src_official, relevance_score=90.0)

    src_weak = make_source(db, "https://youtube.com/watch?v=ggg",
                            "random unrelated short",
                            channel="RandomChannel", is_short=True, published_year=2019)
    m_weak = make_mapping(db, intent, src_weak, relevance_score=20.0)

    selector = FootageSelector(db)
    best = selector.select_best_for_intent(intent.id)
    db.refresh(m_official)
    db.refresh(m_weak)

    check("9a. selector picked the stronger candidate as best",
          best.id == m_official.id, best.id)
    check("9b. best candidate got a non-UNSCORED status",
          m_official.selection_status in (SelectionStatus.AUTO_SELECTED, SelectionStatus.NEEDS_REVIEW),
          m_official.selection_status)
    check("9c. weak/short candidate scored lower than official",
          m_weak.selection_score < m_official.selection_score,
          (m_weak.selection_score, m_official.selection_score))
    check("9d. weak candidate got a clip plan or explicit UNKNOWN reason (planner ran)",
          m_weak.timestamp_confidence is not None, m_weak.timestamp_confidence)
    db.close()


# ---------------------------------------------------------------------
# Test 10: no duplicate mappings are created by selection.
# ---------------------------------------------------------------------
def test_no_duplicate_mappings_created():
    print("\n[10] No duplicate mappings created across reruns")
    db = make_session()
    intent = make_intent(db)
    src = make_source(db, "https://youtube.com/watch?v=hhh", "No Man's Sky official gameplay")
    make_mapping(db, intent, src)

    selector = FootageSelector(db)
    for _ in range(4):
        selector.select_best_for_intent(intent.id)

    count = db.query(AssetMapping).filter(AssetMapping.visual_intent_id == intent.id).count()
    check("10. exactly one mapping still exists after 4 reruns", count == 1, count)
    db.close()


# ---------------------------------------------------------------------
# REJECTED behavior: documented as system-generated / unprotected.
# ---------------------------------------------------------------------
def test_rejected_is_system_writable_not_protected():
    print("\n[R] REJECTED remains system-writable (documented, not protected)")
    db = make_session()
    intent = make_intent(db)
    # A source with no title/description triggers the scorer's hard rejection.
    src = SourceAsset(
        source_url="https://youtube.com/watch?v=iii",
        source_platform="youtube",
        source_channel="Nobody",
        title=None,
        description=None,
        source_duration=100.0,
        published_date=datetime.datetime(2016, 1, 1, tzinfo=datetime.timezone.utc),
        copyright_status=CopyrightStatus.UNKNOWN,
    )
    db.add(src)
    db.commit()
    m = make_mapping(db, intent, src, relevance_score=50.0)

    selector = FootageSelector(db)
    selector.select_best_for_intent(intent.id)
    db.refresh(m)
    check("R1. hard-rejected candidate is REJECTED", m.selection_status == SelectionStatus.REJECTED, m.selection_status)

    # Nothing marks this as a *human* rejection -- it is purely a scorer
    # output, and reruns are free to keep recomputing it (unlike APPROVED).
    m.selection_score = -999  # deliberately corrupt to prove selector will overwrite it
    db.commit()
    selector.select_best_for_intent(intent.id)
    db.refresh(m)
    check("R2. REJECTED mapping's score IS recomputed by rerun (not protected)",
          m.selection_score != -999, m.selection_score)
    db.close()


def run_all():
    print("=" * 70)
    print("V6 CORRECTIVE PATCH -- REGRESSION SUITE")
    print("=" * 70)
    test_approved_is_immutable_across_rerun()
    test_new_higher_scoring_candidate_does_not_demote_approved()
    test_repeated_execution_cannot_overwrite_approved()
    test_concurrent_execution_cannot_overwrite_approved()
    test_non_protected_statuses_still_update_normally()
    test_no_duplicate_mappings_created()
    test_rejected_is_system_writable_not_protected()

    print("\n" + "=" * 70)
    print(f"RESULT: {PASS} passed, {FAIL} failed")
    if FAILURES:
        print("FAILURES:")
        for f in FAILURES:
            print("  -", f)
    print("=" * 70)
    return FAIL == 0


if __name__ == "__main__":
    ok = run_all()
    sys.exit(0 if ok else 1)

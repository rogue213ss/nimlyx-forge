# Nimlyx Forge Architecture

## Core Entity Hierarchy

```text
Channel
 └── Project
      └── Episode
           └── Scene
                └── NarrationSegment
                     └── VisualIntent
                          └── AssetMapping (Stateful Edge)
                               └── SourceAsset (Immutable Physical Asset)
```

## Storage & ORM
Currently using **SQLite + SQLAlchemy** with Alembic for safe migrations.
State machine transitions are strictly enforced in the service layer (`VALID_TRANSITIONS`).

## Discovery Flow
VisualIntents flow through the `DiscoveryService`, which translates semantic requests into strict, platform-specific queries via the `SearchPlanGenerator`. 
Results are mapped into `NormalizedCandidate` and scored by `RelevanceScorer` before being persisted.

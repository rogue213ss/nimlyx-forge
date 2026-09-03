# Nimlyx Forge

Automated production engine for cinematic gaming documentaries.

## Current Architecture

```text
Visual Intent
    ↓
Search Planning
    ↓
YouTube Discovery
    ↓
Relevance Filtering
    ↓
Ranked Candidates
    ↓
Asset Mapping
```

This project is being developed incrementally toward a fully automated pipeline:

```text
Research
→ Story
→ Visual Discovery
→ Asset Acquisition
→ Clip Preparation
→ Timeline Generation
→ Rendering
→ Publishing
```

## Current Project Status: V4 — Strict YouTube Discovery & Relevance Ranking

V4 has successfully implemented:
* structured search planning
* protected game entities
* deterministic relevance scoring
* hard rejection rules
* official-source classification
* YouTube API integration
* asset provenance
* idempotent discovery
* state-based asset workflow
* automated tests

Future functionality (FFmpeg, timeline generation, automated downloads) is NOT yet implemented.

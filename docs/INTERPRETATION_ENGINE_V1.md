# Interpretation Engine v1

Implemented the first rule-based domain: `personality_core`.

## Flow

`astrology.py` → `interpretation_engine.py` → `ai_interpretation.py` → PDF

## Current behavior

- Selects Sun, Moon, Ascendant, Ascendant ruler and Sun aspects.
- Excludes Ascendant, its ruler and houses when birth time is unknown.
- Normalizes Kerykeion sign abbreviations such as `Aqu`, `Tau`, `Lib`.
- Creates traceable dominant patterns, tensions and outer/inner differences.
- Every synthesis item contains internal `evidence_ids`.
- GPT receives structured JSON instead of a free-form chart dump.
- The prompt prohibits exposing internal IDs and requires evidence-backed writing.

## Scope

Only the core-personality domain is rule-based in v1. The factual evidence catalog remains available for report sections that have not yet been migrated. Future modules should cover emotions, communication, relationships, career, money and growth.

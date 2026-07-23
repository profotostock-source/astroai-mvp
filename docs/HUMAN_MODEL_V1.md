# Human Model v1

Human Model v1 is a deterministic symbolic layer between the natal chart and the AI writer.
It is not a psychological test and must not be presented as one.

Pipeline:

Natal chart -> Interpretation Engine -> Human Model -> AI writer -> PDF

The model currently converts Sun, Moon, Ascendant, Ascendant ruler, Mercury, Venus,
Mars, Saturn and Uranus signs into traceable dimensions. Each dimension stores its
supporting chart factors. Numeric scores are internal only and are never printed in the report.

Current output:
- dimensions
- strongest_dimensions
- lower_emphasis_dimensions
- core_tensions
- evidence for each dimension

Next planned step:
- replace generic sign mappings with an editable knowledge base;
- add house and aspect modifiers;
- create separate domain models for relationships, work and communication.

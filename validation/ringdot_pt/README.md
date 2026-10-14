# Ring-dot PT (two-port) and bimorph (internal electrode)

Run by `backend/tests/test_validation_pt.py`. Both are self-consistency checks with exact
expectations, so they test the N-port and internal-electrode machinery independent of material data:

| Check | Expectation |
|---|---|
| Reciprocity | Y12 = Y21 |
| Passivity | Re(Y) positive semi-definite at every frequency |
| Tied ports | dot + ring on one terminal gives exactly Y11 + Y12 + Y21 + Y22 (same mesh) |
| Floating multi-electrode terminal | open-circuit eigen f_a of the tied case = its \|Y\| minimum |
| Bimorph (`validation/bimorph`) | Y = 4 × Y of the single 1.5 mm disc: for extensional modes, opposite poling + centre electrode is equivalent to the single disc at 2 V, with charge from both halves |

A COMSOL comparison for a real PT will be added when reference data is available.

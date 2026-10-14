# PZT-4 disc, a = 10.5 mm, t = 1.5 mm, full-face electrodes

Single-port reference case. Run by `backend/tests/test_validation_disc.py`.

| Quantity | Reference | Source |
|---|---|---|
| Radial f_r | 109.24 kHz | thin-disc formula, η₁ from ηJ₀(η) = (1−σ)J₁(η) |
| Radial f_a | 125.9 kHz | spike `validation/spike_disc` (open-circuit eigen, 84×12 quad8) |
| C at 20 kHz | 2.658 nF (C^T, free) | ε₃₃^T πa²/t; FE is ~1 % higher because 20 kHz is not far below f_r |

The thin-disc formula ignores thickness (a/t = 7), so agreement is expected to ~0.5 %, not exactly.

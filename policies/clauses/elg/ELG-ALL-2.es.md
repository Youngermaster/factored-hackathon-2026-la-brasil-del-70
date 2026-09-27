---
clause_id: ELG-ALL-2
version: 1
jurisdiction: ALL
language: es
effective_from: 2026-09-27
synthetic: true
params:
  risk_cut_medium_bps: 2000
  risk_cut_high_bps: 3500
  borderline_margin_bps: 100
bound_rules: [ELG.risk_estimate_available, ELG.risk_interval_not_borderline]
summary: Uso de la estimación de riesgo sintética y su incertidumbre.
---
La orientación considera una estimación de riesgo calculada por un modelo entrenado con datos sintéticos, con su margen de incertidumbre. Esa estimación nunca se te muestra ni decide por sí sola. Si no está disponible, o si su margen queda cerca del límite entre dos niveles de riesgo, el resultado es que una persona del equipo debe revisar tu caso. Estas reglas son sintéticas y no toman ninguna decisión de crédito.

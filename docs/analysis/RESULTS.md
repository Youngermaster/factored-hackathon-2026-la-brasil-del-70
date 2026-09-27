# Local banking dataset EDA

## Reproducibility and scope

Run: `372ff8010bafd0b4d802`. Generated from inventory dated 2026-09-27T19:36:38.532241+00:00. Git revision: `798e41d8cf1c4538e76533f791fca112681e2c50`. Code fingerprint: `07abc561e1599e1b8dd3a8afe0d793d67b570a9cde6c358bc326a3b6d2e6ba27`.

Scope: all successfully parsed local files. Remote completeness is not verified. Inputs are synthetic organizer data; findings do not estimate real bank performance. Full local lineage and review samples remain excluded from version control.

## Executive summary

This summary is based on the completed local execution `372ff8010bafd0b4d802`, not on a remote or production dataset. The run parsed 23,495,188 rows across 13 tables. Exact duplicate rows and repeated primary keys were not found; 24,029 transcripts were excluded from the curated layer because their required duration is missing. Core customer, product and transaction joins are complete, while branch references and complaint-to-transaction identity need attention. The complaint data do not support a verified link to an originating interaction, and 44,570 affected-product links point to products owned by a different customer. These results expose feasibility constraints for the current dispute-handling project choice; they do not automatically change that choice.

## Inventory

| table | files | bytes | schema_variants | internal_missing_days |
| --- | --- | --- | --- | --- |
| customers | 1 | 46897358 | 1 | 0 |
| products | 1 | 68213646 | 1 | 0 |
| branches | 1 | 89529 | 1 | 0 |
| service_agents | 1 | 237992 | 1 | 0 |
| marketing_campaigns | 1 | 32710 | 1 | 0 |
| transactions | 1097 | 808333639 | 1 | 0 |
| call_center_interactions | 1097 | 139734950 | 1 | 0 |
| call_transcripts | 1097 | 137235657 | 1 | 0 |
| satisfaction_surveys | 1097 | 46446098 | 1 | 0 |
| digital_events | 1097 | 3757355051 | 1 | 0 |
| complaints | 1097 | 17990612 | 1 | 0 |
| campaign_sends | 1083 | 325976325 | 1 | 0 |
| daily_exchange_rates | 1 | 778914 | 1 | 0 |

## Parsing and quality

Files rejected during parsing: 0. Rejected files have unknown row counts and are excluded from analytical denominators.

| table | column | required | denominator | missing | invalid_type |
| --- | --- | --- | --- | --- | --- |
| call_transcripts | duration_seconds | True | 171321 | 24029 | 0 |
| branches | branch_id | True | 350 | 0 | 0 |
| branches | branch_code | True | 350 | 0 | 0 |
| branches | branch_name | True | 350 | 0 | 0 |
| branches | branch_type | True | 350 | 0 | 0 |
| branches | address | True | 350 | 0 | 0 |
| branches | city | True | 350 | 0 | 0 |
| branches | state | True | 350 | 0 | 0 |
| branches | country | True | 350 | 0 | 0 |
| branches | geographic_zone | True | 350 | 0 | 0 |
| branches | phone | True | 350 | 0 | 0 |
| branches | opening_time | True | 350 | 0 | 0 |
| branches | closing_time | True | 350 | 0 | 0 |
| branches | has_atms | True | 350 | 0 | 0 |
| branches | has_teller_windows | True | 350 | 0 | 0 |
| branches | branch_opening_date | True | 350 | 0 | 0 |
| branches | branch_status | True | 350 | 0 | 0 |
| call_center_interactions | interaction_id | True | 686296 | 0 | 0 |
| call_center_interactions | interaction_date | True | 686296 | 0 | 0 |
| call_center_interactions | process_date | True | 686296 | 0 | 0 |
| call_center_interactions | customer_id | True | 686296 | 0 | 0 |
| call_center_interactions | interaction_type | True | 686296 | 0 | 0 |
| call_center_interactions | channel | True | 686296 | 0 | 0 |
| call_center_interactions | contact_reason | True | 686296 | 0 | 0 |
| call_center_interactions | reason_category | True | 686296 | 0 | 0 |
| call_center_interactions | requires_followup | True | 686296 | 0 | 0 |
| call_center_interactions | was_escalated | True | 686296 | 0 | 0 |
| call_center_interactions | has_transcript | True | 686296 | 0 | 0 |
| call_center_interactions | has_recording | True | 686296 | 0 | 0 |
| call_transcripts | transcript_id | True | 171321 | 0 | 0 |

| table | rule | violations | denominator |
| --- | --- | --- | --- |
| complaints | resolved_without_date | 772 | 16121 |
| complaints | claimed_amount_without_currency | 1040 | 21751 |
| products | product_number_unique | 6 | 400000 |
| service_agents | employee_code_unique | 13 | 1200 |

## Conservation of rows

Exact row collapse; required-field failures and conflicting keys excluded. Optional invalid casts become null and remain counted in the profile. Orphans and semantic anomalies stay flagged, not silently dropped.

| table | original_rows | clean_rows | collapsed_duplicates | invalid_required | conflicting_key |
| --- | --- | --- | --- | --- | --- |
| branches | 350 | 350 | 0 | 0 | 0 |
| call_center_interactions | 686296 | 686296 | 0 | 0 | 0 |
| call_transcripts | 171321 | 147292 | 0 | 24029 | 0 |
| campaign_sends | 1746801 | 1746801 | 0 | 0 | 0 |
| complaints | 67095 | 67095 | 0 | 0 | 0 |
| customers | 150000 | 150000 | 0 | 0 | 0 |
| daily_exchange_rates | 13164 | 13164 | 0 | 0 | 0 |
| digital_events | 15620994 | 15620994 | 0 | 0 | 0 |
| marketing_campaigns | 200 | 200 | 0 | 0 | 0 |
| products | 400000 | 400000 | 0 | 0 | 0 |
| satisfaction_surveys | 212759 | 212759 | 0 | 0 | 0 |
| service_agents | 1200 | 1200 | 0 | 0 | 0 |
| transactions | 4425008 | 4425008 | 0 | 0 | 0 |

## Relationships

| child | column | parent | state | nonnull_fk | matched | unmatched | ambiguous_parent_rows | left_join_rows |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| customers | registration_branch_id | branches | measured | 150000 | 5 | 149995 | 0 | 150000 |
| products | customer_id | customers | measured | 400000 | 400000 | 0 | 0 | 400000 |
| products | opening_branch_id | branches | measured | 400000 | 400000 | 0 | 0 | 400000 |
| service_agents | assigned_branch_id | branches | measured | 833 | 2 | 831 | 0 | 1200 |
| transactions | customer_id | customers | measured | 4425008 | 4425008 | 0 | 0 | 4425008 |
| transactions | product_id | products | measured | 4425008 | 4425008 | 0 | 0 | 4425008 |
| transactions | branch_id | branches | measured | 1387932 | 1387932 | 0 | 0 | 4425008 |
| call_center_interactions | customer_id | customers | measured | 686296 | 686296 | 0 | 0 | 686296 |
| call_center_interactions | agent_id | service_agents | measured | 686296 | 686296 | 0 | 0 | 686296 |
| call_transcripts | interaction_id | call_center_interactions | measured | 147292 | 147292 | 0 | 0 | 147292 |
| call_transcripts | customer_id | customers | measured | 147292 | 147292 | 0 | 0 | 147292 |
| call_transcripts | agent_id | service_agents | measured | 147292 | 147292 | 0 | 0 | 147292 |
| satisfaction_surveys | interaction_id | call_center_interactions | measured | 212759 | 212759 | 0 | 0 | 212759 |
| satisfaction_surveys | customer_id | customers | measured | 212759 | 212759 | 0 | 0 | 212759 |
| satisfaction_surveys | agent_id | service_agents | measured | 212759 | 212759 | 0 | 0 | 212759 |
| digital_events | customer_id | customers | measured | 11875548 | 11875548 | 0 | 0 | 15620994 |
| digital_events | product_id | products | measured | 1440338 | 1440338 | 0 | 0 | 15620994 |
| complaints | customer_id | customers | measured | 67095 | 67095 | 0 | 0 | 67095 |
| complaints | affected_product_id | products | measured | 44570 | 44570 | 0 | 0 | 67095 |
| complaints | related_branch_id | branches | measured | 19178 | 19178 | 0 | 0 | 67095 |
| complaints | origin_interaction_id | call_center_interactions | measured | 0 | 0 | 0 | 0 | 67095 |
| complaints | assigned_agent_id | service_agents | measured | 43980 | 43980 | 0 | 0 | 67095 |
| campaign_sends | campaign_id | marketing_campaigns | measured | 1746801 | 1746801 | 0 | 0 | 1746801 |
| campaign_sends | customer_id | customers | measured | 1746801 | 1746801 | 0 | 0 | 1746801 |

| child | parent | identity | matched_rows | mismatches |
| --- | --- | --- | --- | --- |
| transactions | products | customer_id | 4425008 | 0 |
| complaints | products | customer_id | 44570 | 44570 |
| call_transcripts | call_center_interactions | customer_id | 147292 | 0 |
| call_transcripts | call_center_interactions | agent_id | 147292 | 0 |
| satisfaction_surveys | call_center_interactions | customer_id | 212759 | 0 |

## Demand and measured outcomes

| layer | reason | contacts | resolution_known | resolution_rate | escalation_known | escalation_rate | mean_wait_seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| clean | Comercial | 54879 | 54879 | 0.6521 | 54879 | 0.0984 | 120.2065 |
| clean | Producto | 150863 | 150863 | 0.8963 | 150863 | 0.0996 | 119.9632 |
| clean | Queja | 117021 | 117021 | 0.436 | 117021 | 0.1003 | 119.9821 |
| clean | Retención | 20578 | 20578 | 0.6016 | 20578 | 0.0985 | 120.8808 |
| clean | Transaccional | 240056 | 240056 | 0.9151 | 240056 | 0.0993 | 119.6502 |
| clean | Técnico | 102899 | 102899 | 0.6993 | 102899 | 0.1007 | 120.1846 |
| typed | Comercial | 54879 | 54879 | 0.6521 | 54879 | 0.0984 | 120.2065 |
| typed | Producto | 150863 | 150863 | 0.8963 | 150863 | 0.0996 | 119.9632 |
| typed | Queja | 117021 | 117021 | 0.436 | 117021 | 0.1003 | 119.9821 |
| typed | Retención | 20578 | 20578 | 0.6016 | 20578 | 0.0985 | 120.8808 |
| typed | Transaccional | 240056 | 240056 | 0.9151 | 240056 | 0.0993 | 119.6502 |
| typed | Técnico | 102899 | 102899 | 0.6993 | 102899 | 0.1007 | 120.1846 |

| survey_type | responses | valid_scores | mean_csat | nps |
| --- | --- | --- | --- | --- |
| CES | 21235 | 0 | unknown | unknown |
| CSAT | 127856 | 127856 | 2.765243711675635 | unknown |
| NPS | 63668 | 63668 | unknown | -74.50838725890557 |

| currency | transactions | missing_usd | recomputable | conversion_denominator | converted_usd |
| --- | --- | --- | --- | --- | --- |
| ARS | 792585 | 40041 | 40021 | 792338 | 1327904509.08 |
| COP | 1194444 | 59436 | 59421 | 1194084 | 1998134940.29 |
| USD | 2437979 | 2437979 | 2437979 | 2437979 | 4085207957.26 |

Demand aggregates include raw and curated layers with month, country, segment, channel and reason. Unknown dimensions remain visible. Resolution, escalation and follow-up rates use known-value denominators. Duration averages exclude negative or missing values; historical flags do not measure automation safety.

Open complaints are censored; observed resolution duration excludes unresolved cases. CSAT and NPS use their own valid score scales; CES has no documented scale. Currency totals remain separated. USD conversion uses direct positive rates on the event date, without forward filling or replacing source amounts.

## Text and evaluation feasibility

| rows_with_customer_text | exact_groups | normalized_groups | median_characters |
| --- | --- | --- | --- |
| 147292 | 42 | 42 | 82.0 |

| linked_rows | reason_equals_category |
| --- | --- |
| 147292 | 147292 |

| groups | rows |
| --- | --- |
| 42 | 147292 |

| cutoff | earlier_rows | later_rows | later_rows_with_seen_text | later_rows_with_seen_customer |
| --- | --- | --- | --- | --- |
| 2025-11-13 05:50:15 | 117834 | 29458 | 29458 | 16028 |

The temporal probe uses the 80th percentile of linked interaction times. It is not a committed split. Repeated templates, shared customers and post-outcome fields must be controlled before model evaluation. Language codes describe recorded metadata, not independently verified language. Any team-generated Portuguese cases must be identified separately.

## Workflow comparison

| workflow | demand_status | demand_evidence | dependencies | implementation_complexity |
| --- | --- | --- | --- | --- |
| accounts_payments | unknown_at_workflow_granularity | Transactional contacts are a broad proxy; payment inquiries are not separately labeled. | Verify ownership and transaction status; synthetic authenticated read tools required. | medium |
| card_support | unknown_at_workflow_granularity | Product and transactional contacts do not isolate card-service requests. | Requires a card subset, confirmation rules and verified mock block/unblock actions. | medium |
| disputes | unknown_at_workflow_granularity | Complaint categories support a proxy; transaction disputes lack a verified transaction link. | Requires synthetic dispute policy, explicit transaction selection and documented handoff. | high |
| product_information | unknown_at_workflow_granularity | Product contacts are a broad proxy; individual customer holdings are not a public product catalog. | Requires approved or clearly synthetic product terms; no inferred credit eligibility. | medium |

Workflows with all required tables containing usable rows: accounts_payments, card_support, disputes, product_information. Cross-record identity mismatches observed: 44570. Compare account/payment inquiry feasibility against dispute intake using the relationship coverage above. Account/payment inquiries avoid the unverified complaint-to-transaction link, but still require ownership checks. Defer a final workflow choice until contact-label review and identity mismatch resolution. Broad category counts and synthetic outcome flags alone do not justify a winner.

## Next decisions

Review the local stratified text sample, validate label meaning and inspect high-impact relationship failures before selecting the workflow. No final weighted ranking or production benefit is inferred from these synthetic records.

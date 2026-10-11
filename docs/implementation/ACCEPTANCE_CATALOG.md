# Nook acceptance test catalog

The identifiers below are preserved from PRD section 10. Phase test plans decompose them into executable work after implementation. Native/cloud/backup/sync acceptance remains not run.

| ID | Original scope and planned evidence | Owning phases |
| --- | --- | --- |
| T01 | Two named 4 GB phones with distinct chipsets plus a midrange phone; 100 fixed short prompts cold/warm/under pressure; p50/p95 first token/useful answer, decode, peak PSS/RSS, jank, kills, cancel, battery and thermals | 01, requalify 02/06 |
| T02 | Labeled 200-case recall/approval corpus: aliases, unknown/stale/backdated facts, ambiguity, absence, shared photos, hostile OCR; factual fields trace to confirmed IDs; invalid approval rejected; duplicate applies at most once | 01 pilot, 02 full; regression 03–06 |
| T03 | At least 100 English/Filipino/Taglish utterances across speakers/names/numbers/noise; WER and critical entities; TalkBack, large text, focus, denied permissions, transcript correction and offline voices | 01 experiment, 02 selected voice/accessibility, 06 |
| T04 | Provisioned airplane-mode cold start/reboot; save/recall/edit/delete; DB/media/download/upgrade interruption, corrupt assets, full disk; no confirmed-record loss; fixed 15-minute sustained workload | 01 pilot, 02 full; 04/05 extensions |
| T05 | Core privacy with cloud controls off; approved transfers separately; payload equals approved preview; rejection/off blocks calls; seeded secrets absent from logs; outages/revoked permissions | 01 pilot, 02 full; 03–06 feature boundaries |
| T06 | Clean-device restore of proposed 10,000-record/1,000-photo stress fixture; all counts/hashes match; interruption keeps last good backup; missing/corrupt chunks and unsupported schemas rejected | 04 |
| T07 | Correct secret restores; wrong key and login alone cannot decrypt; loss-of-all-devices/secret explanation; key-transfer rollback | 04 |
| T08 | Three clients, duplicate/reordered/delayed operations and ±24-hour skew; event/conflict convergence; no confirmed event lost; stale reconnect cannot resurrect deletion | 05 |
| T09 | Every supported export version; dry-run/import, interruptions, missing assets, collisions; IDs/times/provenance/counts/hashes retained; failure returns to untouched source | 01 mapping pilot, 02 full; 04/05 extension |
| T10 | Place cache reuse, staleness, failed refresh/backoff, boundaries, unknown hours; source/attribution retained; no unapproved endpoint fallback | 02 selected places, 06 |
| T11 | Quotas/retries/concurrency under load; application cost stop; reconciliation to provider billing units within documented tolerance; local functions stay usable | 03 |
| T12 | Declared local/cloud/account deletion across stores/queues/logs/derived caches within chosen SLA; old-device reconnect cannot resurrect data | 02 local subset, 03 cloud subset, 04/05 applicable stores |

## Targets and prerequisites

PRD proposals: warm first token p95 ≤3 seconds, median decode ≥5 tokens/second, cancel ≤500 ms, and zero crash/ANR/OS kill in the inference suite. Speech proposes ≥90% correct intent plus critical entities. These are not measured results or approved commitments. D05/D06 register chosen conditions/thresholds before tests.

The 10,000-record/1,000-photo fixture tests resilience, not promised capacity. A smaller pilot cannot close full T01/T02/T03/T06. Record the pilot subset and outstanding qualification.

For Expo, T01 results identify SDK/React Native/native bridge and bundled build mode. T04 cold launch must work without Metro using an embedded JS bundle; T05 separately checks update/build-service networking and forbids private-data fallback. 01-F11–F13 cover native module/rebuild/config prerequisites.

T04 includes platform speech and backup/transfer behavior. Model failure may disable optional AI but cannot trigger cloud fallback or make confirmed data inaccessible. Every listed factual-authority/approval case must satisfy T02; sampled success is insufficient.

## Case and evidence lookup

- [00 baseline checks](00-readiness/TEST_PLAN.md)
- [01 feasibility](01-feasibility/TEST_PLAN.md)
- [02 local alpha](02-native-local-alpha/TEST_PLAN.md)
- [03 cloud](03-optional-cloud/TEST_PLAN.md)
- [04 backup](04-backup-recovery/TEST_PLAN.md)
- [05 sync](05-device-sync/TEST_PLAN.md)
- [06 expansion](06-expansion/TEST_PLAN.md)

Follow [evidence rules](EVIDENCE_RULES.md) and [requirement traceability](REQUIREMENTS_TRACEABILITY.md). Device matrix, language corpus, deletion SLA, budgets and permitted sources need an accountable decision before their gate closes.

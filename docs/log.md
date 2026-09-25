# Update Log

## 2026-09-25

* **Update**: By owner decision contacts are entered by people only (the `contact` `origin` column is removed, [ADR-10](/architecture/adrs/adr-10-minimal-contact-data.md)); scheduled refresh (`B-15`), source detection (`B-36`), profile enrichment (`B-37`) and the moderated walkthrough (`N-13`, `AC-68`) are P1, with `AC-69` split from `AC-11`; a parent's view never combines subsidiaries' signals, Scoring settings stay Admin-only, and the Labelling screen offers no translation.
* **Update**: [Document conventions](/guidelines/documents/common.md#tooling) state the checker's cross-document rules — cited identifiers, numbering, priority inheritance, the release gate and tags — and every file's `tags` now equal the features whose reading order links it.
* **Update**: The bundle is created for spec-driven development of LeadRadar from the [challenge brief](/reference/challenge-brief.md) and [Annex 1](/reference/annex-1-participant-reference-pack.md): requirements (`RULE-01`–`RULE-10`, `B-01`–`B-35`, `SC-A`–`SC-D`, `S-` and `N-` rows with flows and entities, `AC-01`–`AC-67`), the kernel (SQL store, rules, interfaces `API-01`–`API-70`, overview with the demo dataset), the api, worker and frontend services, eight features with flows `FL-01`–`FL-21`, `ADR-01`–`ADR-14`, guidelines, the generated traceability matrix and the checker.

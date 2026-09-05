# Reviewed flood linkage corrections

The archived CSVs/XLSX and plots remain unchanged. The saved `match_group_id` values were produced by an unavailable matching program. Treating each block as one event can erase different EM-DAT event identities. This review corrects eleven blocks for the correlations analysis and retains all remaining uncertain links.

The retained workbook contains **6,191 flood rows**, while the later CSV contains **6,199**. Its `External IDs` column was omitted from the earlier CSV extraction. The new evidence files preserve that column, original date components, locations and workbook row numbers. EM-DAT defines the year-number portion of `DisNo.` as an event identity; country suffixes identify country records for that event. [Publisher field definitions](https://doc.emdat.be/docs/data-structure-and-content/emdat-public-table/).

Of **271 explicit DFO references**, **231 pass** checks for retained target identity, complete original date precision, country compatibility and overlapping dates. **40 are rejected** with explicit reasons. References alone are insufficient: some point to different years/countries, a missing DFO target, or incomplete/invalid dates. Accepted references remain within existing blocks; none authorize joining whole blocks together.

Ten approved blocks—299, 300, 437, 459, 462, 567, 572, 598, 648 and 652—have every DFO member assigned by these checked publisher references, and separate complete-date EM-DAT event intervals. Each is split into two catalog units. Country records sharing one EM-DAT event identity stay together.

Block 3 receives a separate reviewed correction. Original workbook row **15655** records `2024-0108-BRA`, February 13–16, in Macapá, Amapá. Row **7559** records `2024-0098-BRA`, February 21–23, in Rio de Janeiro State. The former becomes a separate unit. The existing DFO-5516/Rio pair is retained; this review does not upgrade that pair to a publisher-confirmed link.

The corrections preserve all **11,712 raw records**. Canonical catalog units increase **7,434 → 7,445**. Counts at **≥100, ≥1,000 and ≥10,000 reported deaths are unchanged**. Four additional selected records have unknown mortality; no deaths are added or invented. These are catalog identity corrections, not evidence that disasters are physically independent or that coverage is complete.

`merged_floods_long.csv.linkage.json` binds all 35 affected source records to the reviewed catalog/workbook hashes and evidence-file hashes. Changed source material requires renewed review; regeneration fails rather than silently reusing stale decisions. Central `correlations` validates its mirrored contract before every corrected loader call. Its diagnostics retain both the legacy and corrected canonical selections and the before/after count sensitivity. The feeder's archived plots have not been rewritten by this correction.

Reproduce evidence from the unchanged retained inputs:

```bash
python build_linkage_evidence.py
python build_linkage_evidence.py --mirror-catalog ../correlations/data/floods.csv
python -m unittest discover -s tests -v
```

The parser uses Python's standard library. Test fixtures contain small synthetic XLSX files; they do not need the full workbook or a sibling checkout. The builder intentionally refuses source hashes outside the reviewed snapshot. To inspect the remaining ambiguities, run `flood_linkage_audit.py` in the correlations repository; its quarantine remains a review queue, and excluded/unknown records must not be interpreted as zero.

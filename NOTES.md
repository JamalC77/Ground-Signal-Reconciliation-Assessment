# Notes

I approached this assessment as I would most tasks I deal with day to day. I
start with collaborating with AI to expedite my research and understanding of
the problem. I've found GPT-5.4 and Opus 4.6 to be extremely helpful working
through problems and that sometimes one model has a certain insight that the
other lacks for a given instance. Through the assessment I worked in both Claude
Code and Cursor and had the systems check each other's outputs for notable areas
of weakness and edge cases while I verified for accuracy.

I approached the assessment in four phases: normalize each CSV into one internal
record shape, build a deterministic reconciliation core, harden the pipeline
against messy real-world inputs, and then package the result into a reproducible
JSON report. The implementation keeps CSV loading and cleanup at the boundary,
reconciliation logic in pure functions, and report serialization at the output
boundary so each part is easier to review and test.

Lastly, I allowed agents to comb over the project and worked through refining
the quality of the code and tests. I had agents do that after my first full
iteration and I came back and improved upon what was assembled. I've learned
that there are often times where letting a longer running process run to check
for issues or quality concerns can lead to drastically better output. That
output can often be used to refine a quality assessment or improve the tool
that shows the LLM what good looks like as it's building.

Key decisions and assumptions:

- SKU is the identity key after normalization. Name and location are tracked as
  metadata changes, but they do not determine record identity.
- Snapshot schemas are mapped explicitly rather than merged implicitly because
  the two files use different column names for the same concepts.
- Blank header columns are treated as schema errors because they can hide
  shifted or extra data during CSV row mapping.
- Rows with more values than headers are rejected as malformed instead of
  silently truncating extra columns during CSV mapping.
- Duplicate SKUs are not merged. The first occurrence is kept, and conflicting
  duplicates are surfaced as reviewable issues instead of being summed or
  overwritten silently.
- Whole-number float quantities such as `70.0` are coerced losslessly to `int`,
  while fractional or invalid quantities are rejected and logged as quality
  issues.
- Negative quantities are preserved but flagged for manual review rather than
  corrected automatically.
- File-level temporal validation checks that each snapshot is internally date
  consistent and that the current snapshot does not predate the older one.

Data quality issues found in the provided files:

- Three snapshot 2 SKUs required normalization (`SKU005`, `sku-008`, `SKU018`).
- `SKU-045` appears twice in snapshot 2 with conflicting values, and the second
  row also has a negative quantity (`-5`).
- Several fields contained leading or trailing whitespace that needed trimming.
- Two quantities were stored as whole number floats (`70.0`, `80.00`).
- One date used `MM/DD/YYYY` instead of ISO format.
- Snapshot 1 includes a trailing blank row that is skipped during loading.

Final reconciliation outcome:

- 73 items are present in both snapshots.
- 2 items appear only in snapshot 1 (`SKU-025`, `SKU-026`).
- 5 items appear only in snapshot 2 (`SKU-076` through `SKU-080`).
- 71 matched items decreased in quantity, 2 were unchanged, and none increased.
- 1 matched item (`SKU-045`) had a product name change.
- 14 total quality issues were logged, with 2 flagged for manual review in the
  final report.
- The reconciliation logic handles the quality issues present in these snapshots
  and produces a result I would trust for this dataset.

Future hardening considerations:

- I intentionally stopped short of implementing every possible safeguard here
  because that would have been overengineering for an assessment-sized solution.
- For production-grade warehouse exports, I would add validation for repeated
  header or footer rows, shifted columns, Excel-damaged SKUs, delimiter or
  encoding drift, and cases where the true identity key is `(sku, location)`
  rather than `sku` alone.
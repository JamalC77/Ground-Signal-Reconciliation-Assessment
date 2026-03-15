# Data Audit

I asked Claude Opus 4.6 to do a deep dive on both snapshot files before any code was written, looking for structural mismatches, formatting inconsistencies, and edge cases that could quietly produce wrong reconciliation results.  I then manually reviewed the findings and verified their accuracy.
The findings below informed the normalization and quality-handling decisions in the build plan.

Findings are ordered by severity starting with problems that would silently produce wrong results, ending with cosmetic issues that are still worth logging.

## Schema Mismatch

The two snapshots use entirely different column headers for the same data:


| Snapshot 1     | Snapshot 2     | Canonical Field |
| -------------- | -------------- | --------------- |
| `name`         | `product_name` | name            |
| `quantity`     | `qty`          | quantity        |
| `location`     | `warehouse`    | location        |
| `last_counted` | `updated_at`   | date            |


Only `sku` is shared. This rules out any naive merge on columns approach and requires an explicit mapping layer before comparison can begin.

## Identity Issues (SKU)

Three rows in snapshot 2 have malformed SKUs that would cause false add and remove pairs if not normalized before joining:


| Snap 2 Line | Raw SKU   | Problem        | Resolves To |
| ----------- | --------- | -------------- | ----------- |
| 6           | `SKU005`  | missing hyphen | `SKU-005`   |
| 19          | `SKU018`  | missing hyphen | `SKU-018`   |
| 9           | `sku-008` | lowercase      | `SKU-008`   |


Without normalization, each of these would appear as one removed item and one added item - the exact kind of plausible but wrong output that makes reconciliation dangerous.

## Duplicate SKU with Conflicting Data

The most complex issue in the dataset. `SKU-045` appears twice in snapshot 2 with contradictory values:


| Line | Name                    | Quantity | Location    |
| ---- | ----------------------- | -------- | ----------- |
| 44   | Multimeter Professional | 23       | Warehouse A |
| 54   | Multimeter Pro          | -5       | Warehouse B |


These rows disagree on name, quantity, and warehouse. The second occurrence also carries a negative quantity, which compounds the ambiguity. It could be a data entry error, a leaked adjustment record, or a multi-location entry that doesn't belong in a flat snapshot.

The reconciliation system retains the first occurrence and logs the duplicate. Summing or silently picking "last wins" would risk incorporating the negative quantity into a delta calculation without any audit trail.

## Negative Quantity

The duplicate `SKU-045` row (snap 2, line 54) has a quantity of `-5`. Physical inventory cannot be negative. Regardless of how the duplicate is handled, this value gets flagged as a quality issue.

## Whitespace Contamination

Several name fields contain leading or trailing whitespace that would cause false name change detections if not stripped:


| File       | Line | Raw Value                | Type     |
| ---------- | ---- | ------------------------ | -------- |
| Snapshot 1 | 36   | `Cable Ties 100pk`       | trailing |
| Snapshot 1 | 53   | `Compressed Air Can`     | leading  |
| Snapshot 2 | 3    | `Widget B`               | leading  |
| Snapshot 2 | 11   | `Mounting Bracket Large` | trailing |
| Snapshot 2 | 22   | `HDMI Cable 3ft`         | both     |


Stripping is non-destructive and happens during normalization. Original values are preserved in the quality log.

## Quantity Type Inconsistency

Two rows in snapshot 2 store integer quantities as floats:


| Line | SKU     | Raw Value |
| ---- | ------- | --------- |
| 3    | SKU-002 | `70.0`    |
| 8    | SKU-007 | `80.00`   |


These happen to be whole numbers, so `int(float(x))` is lossless. But the coercion is logged so that a genuinely fractional value (e.g., `70.5`) would surface as a data quality issue rather than being silently truncated.

## Date Format Inconsistency

Snapshot 2, line 34 uses `01/15/2024` (MM/DD/YYYY) while every other row across both files uses `2024-01-15` (ISO 8601). Normalized to ISO during loading; original format logged.

## Product Name Change

`SKU-045` is called `Multimeter Pro` in snapshot 1 and `Multimeter Professional` in snapshot 2. This is a legitimate metadata change - not a data quality defect, but it is worth surfacing in the reconciliation report. Name is informational; SKU is the identity key.

## Removed Items

Two SKUs present in snapshot 1 are absent from snapshot 2:


| SKU     | Name      | Last Quantity | Location    |
| ------- | --------- | ------------- | ----------- |
| SKU-025 | VGA Cable | 50            | Warehouse B |
| SKU-026 | DVI Cable | 35            | Warehouse B |


Both are legacy video interconnects. Consistent with discontinuation or sellthrough.

## Added Items

Five SKUs appear in snapshot 2 with no corresponding entry in snapshot 1:


| SKU     | Name              | Quantity | Location    |
| ------- | ----------------- | -------- | ----------- |
| SKU-076 | Stream Deck Mini  | 15       | Warehouse A |
| SKU-077 | Stream Deck XL    | 8        | Warehouse A |
| SKU-078 | Capture Card      | 12       | Warehouse A |
| SKU-079 | USB-C Hub         | 45       | Warehouse A |
| SKU-080 | Thunderbolt Cable | 30       | Warehouse A |


All are streaming and USB-C accessories, all located in Warehouse A. The clustering suggests a single intake event for a new product line.

## Trailing Blank Lines

Snapshot 1 has two empty lines at EOF (lines 77 and 78). These need to be discarded during loading to avoid producing rows with empty fields.

## Quantity Delta Pattern

Every matched item either stayed flat or decreased. No item increased in quantity between snapshots. The only two unchanged items are SKU-006 (Connector Cable 10ft) and SKU-007 (Power Supply Unit). This is consistent with a week of outbound activity and no restocking, which is not a defect but is useful context when validating the reconciliation output. An unexpected increase would warrant closer inspection.

## Design Decisions Derived from This Audit


| Finding                      | Decision                                                                                  |
| ---------------------------- | ----------------------------------------------------------------------------------------- |
| Different column schemas     | Explicit column mapping per snapshot, resolved to canonical fields before comparison      |
| Malformed SKUs               | Normalize case and format (uppercase, insert hyphen) as part of identity canonicalization |
| Duplicate SKU                | First occurrence wins; duplicate logged as quality issue                                  |
| Negative quantity            | Flagged; value preserved but surfaced in quality report                                   |
| Whitespace in names          | Strip all string fields; log original values                                              |
| Float quantities             | Cast through `float` → `int`; log coercion; flag true fractionals                         |
| Non-ISO date                 | Normalize to `YYYY-MM-DD`; log original format                                            |
| Name change across snapshots | Report as informational change; does not affect identity matching                         |
| Blank trailing rows          | Skip rows with empty SKU during loading                                                   |



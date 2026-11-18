# Sheet Solution — User Guide (plain English)

This is for the person who receives the sheet, **not** a developer. You do
not need to know any programming language.

## You have two jobs

1. Tell the tool **what to look for** (fill the template).
2. Run it and **read the report**.

That's it. The tool does the checking; you do the telling and the reading.

## Step 1 — Fill the template

Open `examples/check-template.example.txt` (or ask for a blank one). It is a
list of boxes. For each thing you want to check, fill one box:

```
[CHECK]
check_id = CH-001                        <- a short id, any letters/numbers
what_is_this_check_for = Every applicant has a passport photo
what_to_look_at = the passport_photo column
expected_value_or_rule = no blank         <- what counts as a PASS
when_it_fails_say = No passport photo for this applicant
machine_can_check = yes                  <- yes = the tool checks it; no = you look
column_name = passport_photo             <- which column (spreadsheets only)
example_that_passes = a row that has a photo
example_that_fails = a row with no photo
```

### The rules you can use for `expected_value_or_rule`

| You want to check… | Write in the box |
|---|---|
| A value must exist (not empty) | `no blank` |
| A value must be exactly X | `must equal X` |
| A number must be at least X | `>= X` |
| A number must be at most X | `<= X` |
| Something a machine can't judge (e.g. "is the photo clear?") | `machine_can_check = no` and add a `human_review_note` |

### If you set `machine_can_check = no`

The tool will **not** guess. It will pull the image out to
`out/report/media/`, mark the check `PENDING-HUMAN`, and wait for **you** to
look at it. Then you open the image and decide. The tool writes down *that you
decided* — who and when — in the log. This is a human check, logged. It is
honest: the tool never tells you a photo is "fine" on its own.

## Step 2 — Run it

**Easiest (non-technical):**

```
./run.sh your-sheet.xlsx your-checks.txt out/report
```

**Or with the CLI:**

```
python -m sheet_solution run --sheet your-sheet.xlsx --template your-checks.txt --out out/report
```

**Or click through the browser:** `python gui/main.py`, open
`http://127.0.0.1:8477`, paste your paths, click **Run checks**.

## Step 3 — Read the report

Open `out/report/check-results.csv` (Excel opens it directly):

| column | what it means |
|---|---|
| `outcome` | `PASS` · `FAIL` · `PENDING-HUMAN` |
| `matched_rows` / `failed_rows` / `denominator` | how many rows passed / failed / were checked |
| `failed_row_ids` | exactly which rows failed — go fix those |
| `detail` | a plain-English sentence about the check |

- `FAIL` → look at `failed_row_ids`, that's what didn't pass.
- `PENDING-HUMAN` → open the image in `out/report/media/`, confirm it, and
  note your decision.
- The summary line at the top of the run tells you the counts.

## Proving it later

```
python -m sheet_solution verify --out out/report
```

If anything in the pack was changed after you ran it, this tells you. A clean
pack prints `VERIFIED-STRUCTURE`.

## Privacy

Nothing you run is sent anywhere. The tool works on your machine, fully
offline. Passport photos and personal data stay on your device.

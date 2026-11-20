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
# (add --key <column> to name which column identifies each row; auto-detected otherwise)
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

The run also writes `out/report/.audit/ledger.jsonl`, an intent/result chain
for the run itself:

```
python -m sheet_solution ledger --out out/report verify    # chain intact?
python -m sheet_solution ledger --out out/report pending   # interrupted runs
```

A normal run leaves no pending intents. If the tool was stopped mid-run, the
intent is still there and `pending` shows it — you can see the run did not
finish instead of trusting a partial report.

## "The check failed — now what do I do about it?"

That's the **decision loop**. The tool never changes your data on its own. It
turns each failed check into a *proposal* and waits for you. In a policy file
you decide what options a failure may offer (for example `tag_row` or
`flag_for_human`); if you name none, the safe "flag it for a person" option is
always offered.

After a `run`, from the terminal:

```
# 1. see the proposals (written to decisions.json in the run pack)
python -m sheet_solution decisions plan --out out/report --policy policy.json
python -m sheet_solution decisions list --out out/report

# 2. make a decision — every step needs a named person (--actor)
python -m sheet_solution decisions decide --out out/report --finding-id F-... \
  --action decline --actor alice --reason "needs a human"
python -m sheet_solution decisions decide --out out/report --finding-id F-... \
  --action re-propose --actor bob --action-id flag_for_human
python -m sheet_solution decisions decide --out out/report --finding-id F-... \
  --action approve --actor carol

# 3. only now apply it — approving alone changes nothing
python -m sheet_solution decisions decide --out out/report --finding-id F-... \
  --action apply --actor carol
```

The important part: **saying no never hides your options.** If you decline an
action, the tool applies nothing and shows the remaining options (plus a
"flag for a person" path). You pick another, and it still waits for an
approval before doing anything. Only `apply` writes a corrected copy
(`corrected-copy.jsonl`), and only for a decision you approved. Every step is
recorded in the ledger with who did it, so you can prove what was decided.

**In the GUI:** open the **Decide** tab. Drop your policy file, confirm the run
pack path (it fills in after you run checks in tab 01), type your name, and
click **Plan decisions**. Each finding becomes a colour-coded card. **Decline**
applies nothing and reveals an alternative; pick one and use **Use
alternative**, then **Approve**, then **Apply**. The card's colour and badge
show the current state, so you can always see what has and has not been done.

## "I have two sheets that should match — what changed?"

That's the **compare** task. Instead of filling a check-template, you tell
the tool the two sheets, the column that names "the same thing" (the row
key), and the columns to compare.

**In the GUI:** open the **Compare two sheets** tab, drop Sheet A and Sheet
B, type the key + columns, click **Compare**. You get colour-coded cards:
green = matched, red = changed, blue = only in A, orange = only in B.

**From the terminal:**

```
python -m sheet_solution compare \
  --sheet-a baseline.xlsx --sheet-b new.xlsx \
  --key applicant_id --fields amount,status \
  --out out/compare
```

The report (`out/compare/compare-report.csv`) shows, per item: which fields
changed and the value on each side. Numbers can be compared with a tolerance
(`--tolerance 0.1` means "within 0.1 is still the same"); leave it blank for
exact. It's a count you can defend, not a "looks the same."

## Using the drag-and-drop screen

If you don't like the terminal, open the screen:

```
pip install "sheet-solution[gui]"
python -m sheet_solution.gui.main      # opens http://127.0.0.1:8477
```

Drag your files into the boxes, click **Run** / **Compare**, and read the
cards. Everything happens on this computer.

## Privacy

Nothing you run is sent anywhere. The tool works on your machine, fully
offline. Passport photos and personal data stay on your device.

"""
Set the Shariah-compliance flag on each company in data_md/psx_financials.md.

Single source of truth = the COMPLIANT list below (edit it and re-run anytime).
Every company whose ticker is in COMPLIANT gets a `Shariah Compliant: Yes` line;
all others get `Shariah Compliant: No` — nothing else. The script strips any
existing flags first, so it is safe to run repeatedly.

Run from the repo root:
    python scripts/set_shariah_flags.py
"""
import re

MD = "data_md/psx_financials.md"

# --- EDIT THIS: PSX tickers that ARE Shariah-compliant -----------------------
COMPLIANT = {
    "MEBL", "LUCK", "ENGROH", "GHNI", "SYS", "HUBC", "FFC", "MARI", "EFERT",
    "PPL", "MLCF", "FCCL", "AIRLINK", "PSO", "DGKC", "GAL", "OGDC", "NML",
    "NRL", "PAEL", "PRL", "HCAR", "FFL", "SEARL", "CPHL", "ATRL", "TREET",
    "SSGC", "SNGP", "SAZEW",
}
# -----------------------------------------------------------------------------

H1 = re.compile(r"^#\s+([A-Za-z0-9]+)\s+-\s+(.+?)\s*$")
FLAG = re.compile(r"^_?shariah compliant:", re.IGNORECASE)


def main():
    with open(MD, encoding="utf-8") as f:
        text = f.read()

    # 1) strip existing flag lines
    lines = [ln for ln in text.splitlines() if not FLAG.match(ln.strip())]

    # 2) collapse runs of blank lines to a single blank (cleans up after removal)
    collapsed = []
    for ln in lines:
        if ln.strip() == "" and collapsed and collapsed[-1].strip() == "":
            continue
        collapsed.append(ln)

    # 3) inject a fresh flag under each company H1
    out, yes, no = [], [], []
    for ln in collapsed:
        out.append(ln)
        m = H1.match(ln.strip())
        if not m:
            continue
        ticker = m.group(1).upper()
        if ticker in COMPLIANT:
            out += ["", "Shariah Compliant: Yes"]
            yes.append(ticker)
        else:
            out += ["", "Shariah Compliant: No"]
            no.append(ticker)

    with open(MD, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")

    missing = sorted(COMPLIANT - set(yes))
    print(f"compliant flagged : {len(yes)}")
    print(f"non-compliant     : {len(no)}")
    if missing:
        print(f"in COMPLIANT list but NOT found in the dataset: {missing}")
    print(f"non-compliant tickers: {sorted(no)}")


if __name__ == "__main__":
    main()

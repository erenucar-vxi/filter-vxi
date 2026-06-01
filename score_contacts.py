#!/usr/bin/env python3
"""
score_contacts.py — Score a 6sense CSV export for VXI BDM outreach using Groq.

Usage:
    python score_contacts.py input.csv output.csv
    python score_contacts.py input.csv output.csv --model llama-3.3-70b-versatile
    python score_contacts.py input.csv output.csv --delay 2.5

Requires:
    pip install -r requirements.txt

API key (pick one):
    export GROQ_API_KEY=your_key_here          # environment variable
    echo 'GROQ_API_KEY=your_key_here' > .env   # .env file (never commit this)

Get a free Groq API key at https://console.groq.com
"""

import os
import sys
import time
import argparse

import pandas as pd
from openai import OpenAI
from tqdm import tqdm

# Load .env if present (requires python-dotenv, silently skipped if absent)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ─── CLI ──────────────────────────────────────────────────────────────────────

parser = argparse.ArgumentParser(
    prog="score_contacts",
    description="Score 6sense contacts for VXI BDM outreach using Groq Llama.",
    formatter_class=argparse.RawDescriptionHelpFormatter,
    epilog=__doc__,
)
parser.add_argument("input",  help="Path to input CSV")
parser.add_argument("output", help="Path to write scored CSV")
parser.add_argument(
    "--model",
    default="llama-3.3-70b-versatile",
    help="Groq model ID (default: llama-3.3-70b-versatile)",
)
parser.add_argument(
    "--delay",
    type=float,
    default=2.1,
    metavar="SECONDS",
    help="Pause between requests in seconds (default: 2.1). Groq free tier: 30 req/min.",
)
parser.add_argument(
    "--keep-only",
    action="store_true",
    help="Write only KEEP rows to the output file.",
)
args = parser.parse_args()

# ─── API key ──────────────────────────────────────────────────────────────────

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()
if not GROQ_API_KEY:
    print(
        "Error: GROQ_API_KEY is not set.\n"
        "  export GROQ_API_KEY=your_key_here\n"
        "  — or — create a .env file with: GROQ_API_KEY=your_key_here\n"
        "  Get a free key at https://console.groq.com",
        file=sys.stderr,
    )
    sys.exit(1)

# ─── Prompt ───────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are a sales-ops analyst at VXI Global Solutions, a BPO that sells outsourced \
customer experience and contact center services. Buyers own or influence decisions \
about customer support, customer experience, contact centers, vendor management, or operations.

For each contact, output exactly two lines and nothing else:
DECISION: KEEP | DROP | REVIEW
REASON: <one short phrase under 12 words>

KEEP if all true:
1. Seniority is Director, VP, SVP, EVP, C-level, Chief, Head of, or President
2. Title or function shows ownership of CX, customer care, customer service, \
customer support, contact center, call center, support operations, CX strategy, \
vendor management, BPO procurement, or operations leadership with CX in scope
3. Company is a real operating company (not staffing/recruiting/BPO competitor)

DROP if any true:
- Seniority is Manager, Senior Manager, Lead, Analyst, Coordinator, Specialist, IC, or unspecified
- Function is engineering, software, IT, data science, security, product, design, \
marketing (unless CX-marketing), sales (unless CX-sales), legal, HR, unrelated finance, \
R&D, or clinical
- Company is a BPO competitor: Teleperformance, Concentrix, TTEC, Alorica, Sitel, \
Foundever, Sutherland, Conduent, Genpact, iQor, Webhelp, Majorel, ResultsCX
- Company is a recruiting/staffing/consultancy

REVIEW if:
- Title is Director/VP of Procurement or Vendor Management
- Title is vague (Director of Operations with no clarifier)
- Title and function fields conflict
- Seniority is high but role fit ambiguous

Tie-breaker: when in doubt, DROP.\
"""

FIELDS_USED = [
    "First Name", "Last Name", "Company Name",
    "Job Title", "Seniority", "Job Function",
]

# ─── Setup ────────────────────────────────────────────────────────────────────

client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1",
)

try:
    df = pd.read_csv(args.input)
except FileNotFoundError:
    print(f"Error: file not found: {args.input}", file=sys.stderr)
    sys.exit(1)

print(f"Loaded {len(df):,} rows from {args.input}")
print(f"Model : {args.model}")
print(f"Delay : {args.delay}s between requests")
print(f"Est.  : {len(df) * args.delay / 60:.1f} minutes\n")

missing = [f for f in FIELDS_USED if f not in df.columns]
if missing:
    print(f"Warning: missing expected columns: {missing}")
    print(f"Available columns: {list(df.columns)}\n")

# ─── Scoring loop ─────────────────────────────────────────────────────────────

decisions: list[str] = []
reasons:   list[str] = []

for idx, row in tqdm(df.iterrows(), total=len(df), desc="Scoring", unit="contact"):
    contact_text = "\n".join(
        f"{field}: {row[field]}"
        for field in FIELDS_USED
        if field in df.columns and pd.notna(row[field]) and str(row[field]).strip()
    )

    retries = 3
    backoff = 30
    scored = False

    while retries > 0 and not scored:
        try:
            response = client.chat.completions.create(
                model=args.model,
                max_tokens=80,
                temperature=0.1,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": f"Contact:\n{contact_text}\n\nDecide:"},
                ],
            )
            output = response.choices[0].message.content.strip()

            decision = "ERROR"
            reason   = "Could not parse"

            for line in output.splitlines():
                line = line.strip()
                if line.upper().startswith("DECISION:"):
                    raw = line.split(":", 1)[1].strip().upper()
                    decision = raw if raw in ("KEEP", "DROP", "REVIEW") else "REVIEW"
                elif line.upper().startswith("REASON:"):
                    reason = line.split(":", 1)[1].strip()

            decisions.append(decision)
            reasons.append(reason)
            scored = True

        except Exception as exc:
            err = str(exc).lower()
            if "rate" in err or "429" in err:
                tqdm.write(f"  Rate limited on row {idx} — waiting {backoff}s…")
                time.sleep(backoff)
                backoff = min(backoff * 2, 120)
                retries -= 1
            else:
                tqdm.write(f"  Error on row {idx}: {exc}")
                decisions.append("ERROR")
                reasons.append(str(exc)[:60])
                scored = True

    if not scored:
        decisions.append("ERROR")
        reasons.append("Max retries exceeded")

    time.sleep(args.delay)

# ─── Output ───────────────────────────────────────────────────────────────────

df["Decision"] = decisions
df["Reason"]   = reasons

out = df[df["Decision"] == "KEEP"] if args.keep_only else df
out.to_csv(args.output, index=False)

counts = pd.Series(decisions).value_counts()
total  = len(decisions)
print(f"\n{'─'*40}")
print(f"Output : {args.output}  ({len(out):,} rows written)")
print(f"KEEP   : {counts.get('KEEP',   0):>5,}  ({counts.get('KEEP',   0)/total*100:4.1f}%)")
print(f"DROP   : {counts.get('DROP',   0):>5,}  ({counts.get('DROP',   0)/total*100:4.1f}%)")
print(f"REVIEW : {counts.get('REVIEW', 0):>5,}  ({counts.get('REVIEW', 0)/total*100:4.1f}%)")
print(f"ERROR  : {counts.get('ERROR',  0):>5,}")
print(f"{'─'*40}")

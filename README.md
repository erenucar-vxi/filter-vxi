# VXI Contact Scorer

Score a 6sense CSV export for BDM outreach using [Groq](https://console.groq.com)'s Llama 3.3 70B.
Each contact gets a **KEEP / DROP / REVIEW** decision plus a short reason phrase.

---

## Web App (GitHub Pages)

Visit the live app at:
```
https://turatzheksheev-vxi.github.io/filterVXI/
```

1. Get a free Groq API key at [console.groq.com](https://console.groq.com)
2. Enter the key in Step 1 (stored only in your browser tab — never sent anywhere except Groq)
3. Upload your 6sense CSV export
4. Click **Start Scoring** and watch results appear live
5. Download the scored CSV when done

### Enabling GitHub Pages (one-time setup)
Go to **Settings → Pages → Source** and select **GitHub Actions** as the source.
The included workflow (`pages.yml`) deploys automatically on every push to `main`.

---

## Python CLI

### Setup
```bash
pip install -r requirements.txt
```

### API key
```bash
# Option A — environment variable
export GROQ_API_KEY=your_key_here

# Option B — .env file (never commit this file)
echo 'GROQ_API_KEY=your_key_here' > .env
```

### Run
```bash
python score_contacts.py input.csv output.csv
```

### Options
```
positional arguments:
  input            Path to input CSV
  output           Path to write scored CSV

options:
  --model MODEL    Groq model ID (default: llama-3.3-70b-versatile)
  --delay SECONDS  Pause between requests (default: 2.1)
  --keep-only      Write only KEEP rows to output
```

### Examples
```bash
# Basic
python score_contacts.py export.csv scored.csv

# Faster model, keep-only output
python score_contacts.py export.csv leads.csv --model llama-3.1-8b-instant --keep-only

# Test with sample data
python score_contacts.py sample_input.csv sample_output.csv
```

---

## Expected CSV columns

| Column | Required | Notes |
|---|---|---|
| `First Name` | yes | |
| `Last Name` | yes | |
| `Company Name` | yes | |
| `Job Title` | yes | |
| `Seniority` | yes | Director, VP, C-Level, etc. |
| `Job Function` | yes | Customer Experience, Engineering, etc. |

Missing columns trigger a warning but do not abort — the scorer works with whatever fields are present.

---

## Scoring logic

| Decision | Criteria |
|---|---|
| **KEEP** | Director+ seniority · CX/contact-center function · real operating company |
| **DROP** | Manager-level or below · non-CX function · BPO competitor · staffing firm |
| **REVIEW** | Procurement/vendor titles · vague Director of Operations · conflicting signals |

Groq free tier: 30 requests/minute. Default delay is 2.1 s between requests (~28 req/min).

---

## Security

- **Never commit your `.env` file** — it's in `.gitignore`
- **Never commit real contact CSVs** — all `*.csv` files except `sample_input.csv` are gitignored
- The web app sends contact data only to `api.groq.com` — no other server is involved

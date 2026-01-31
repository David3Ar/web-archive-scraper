# SE Backup – Playwright

Backup tool for the SE assignment platform using Playwright (Python).

Creates PDFs of assignments and optionally downloads attachments.
Everything is controlled via a single config file per Website.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
# Windows: .\.venv\Scripts\Activate.ps1

pip install -r requirements.txt
playwright install chromium
```

## Run 
```
cd app
python se_config.py
```

## Config

Copy or edit `se_config.py`.

You can configure:
- assignments vs submissions
- which resources to download (`mode=dl`, `pdf`, etc.)
- output options
- allowed hosts

## Output
Files are written to `data/` (one folder per assignment).
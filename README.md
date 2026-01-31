# web-archive-scraper
Playwright-based scraper for archiving content from university platforms like Moodle and 'Roeselite' ;).
  
The tool is configuration-driven.
All behavior is defined via Pythondataclass configs.
  
  
### Setup
_Create venv, install dependencies, install Playwright browser._

```bash
python -m venv .venv
source .venv/bin/activate
# Windows: .\.venv\Scripts\Activate.ps1

pip install -r requirements.txt
playwright install chromium
```

### Run 
Execute the config file of a course.

First run requires interactive CLI login.  
Session data is stored in the configured profile directory.

Example:
```
python app/configs/se_config.py
python app/configs/theoinf_config.py
```

### Config
Each course has its own config file and inherits from a platform-specific config: `MoodleConfig` | `RoeseliteConfig`

You can create your own config file for any other module running on 'Moodle' or 'Roselite' platform. 


#### Common Configuration Options

| Option | Description |
|--------|-------------|
| out_dir | Base output directory. Can be any path. |
| profile_dir | Directory for persistent Playwright profile (cookies, session). |
| headless | Run browser headless (True) or with UI (False). |
| start_path | Entry URL or path for the course. |
| replace_existing_files | Overwrite existing files if enabled or skip if disabled |

_Find config files in `app/base_config/` and discover all configuration options._
  
  
#### Platform Notes
  
##### Moodle: 
- Scraping is controlled via module path patterns
- Only matching modules are processed
  
##### Roselite: 
- Navigation and output behavior is platform-specific
- Multiple download formats _(e.g. pdf, raw, zip, tgz)_ can be enabled in configuration

## Output
All files are written relative to specified `out_dir`.


TODO:
Roeselite: slide downloads
Moodle: test alternative layouts / modules
Output: enable relative or absolute out_dir


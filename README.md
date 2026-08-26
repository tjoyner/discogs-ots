```markdown
# Discogs Information Retrieval Application

A Python application designed to extract the information from Discogs need for creation of library records.

---

## Features

* **Multi-Format Export:** Generates a CSV file and can optionally generate MarcEdit mnemonic text (`.mrk`) files.
* **Hierarchical Written-By Resolution:**
  * Checks track-level extraartists for written-by credits.
  * Falls back to album level extraartists for written-by credits per track.
  * Falls back to album level extraartists for written-by credits for the entire album 
* **If track or extraartist information is missing, it can optionally search the master record or the main release entry (if different than the record
  being processed).
* **Track Range Expansion:** Automatically parses top-level track-writing assignments (e.g., converting `"A1, A3 to A5"` or `"B1-2"` into explicit track positions mapped to individual track records). If expansion is not possible, an error is logged.
* **Flexible Fetching Modes:** Process individual release IDs, batch process list files, or query a user's entire Discogs collection folder.
* **Optional Diagnostics:** Generates raw API JSON dumps and detailed operation logs.

---

## Installation

Ensure you have Python 3.8 or later installed. Install the required dependency:

```
pip install discogs-client

```

To run the test cases, install the following dependency:
pip install pytest

---

## Usage & Command-Line Arguments

Run the script directly on the command line:

```bash
python ./discogs_ots.py -c ../../ots.ini  -o ../../ots_0815.csv -qi

```

Run the test cases:
```bash
python pytest

```

### Options Breakdown

| Argument | Short | Description |
| --- | --- | --- |
| `--input-file` | `-i` | Path to the input file containing a list of Discogs release IDs, one per line. Anything after the ID is ignored. |
| `--release-id` | `-id` | Process a single Discogs Release ID. |
| `--query-for-ids` | `-qi` | Query the user's Discogs collection for release IDs. user-token must also be specified.|
| `--new-records-only` | `-nro` | Query the user's Discogs collection for release IDs that aren't in the input list. Requires
--query-for-ids and --input-file. |
| `--output-file` | `-o` | The output CSV file |
| `--log-file` | `-l` | Path to the file where log messages will be saved. If not specified, the log file is 'output-file'.log |
| `--user-agent` | `-ua` | User-Agent to use for Discogs API requests |
| `--user-token` | `-ut` | User token (generated at Discogs site) to use for authenticated API requests |
| `--ignore-roles` | `-ir` | Comma-separated list of artist roles to skip (e.g., `Design, Cover`). |
| `--check-master` | `-cm` | Check the master record (if one exists) for a track list if not found in the record. |
| `--check-main-release` | `-cmr` | Check the main release record (if it exists and is different from the release ID) for extra artists. |
| `--write-mrk` | `-mrk` | (Experimental) Write a MARC .mrk file in addition to the csv file. |
| `--log-all-roles` | `-lar` | Log all artist roles encountered (not including configured ignored roles). |
| `--dump-json` | `-dj` | Dump the raw Discogs json response into output-file'.json |
| `--config` | `-c` | Path to an `.ini` configuration file. |


---

## Configuration (`config.ini`)

You can configure options using a standard INI configuration file instead of passing command-line arguments:

```ini
[api]
user_agent = MyCatalogApp/1.0
user_token = YOUR_DISCOGS_USER_TOKEN

[settings]
input_file = input_ids.txt
output_file = catalog_output.csv
log_file = processing.log
write_mrk = False
check_master = True
check_main_release = True
ignore_roles = Cover, Design, Photography

```

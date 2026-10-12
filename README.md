# PDF Compressor

A small web app that compresses PDFs with [Ghostscript](https://ghostscript.com/). It is built with Flask. You can upload one file or many. Many files come back as a single ZIP.

## Features

- Bulk upload. A single file is returned as a PDF and multiple files as a ZIP.
- Three presets:

  | Preset | Ghostscript setting | Resolution | Result |
  |---|---|---|---|
  | Smallest file | `/screen` | 72 dpi | Smallest file, lowest quality |
  | Balanced (default) | `/ebook` | 150 dpi | Good quality at a moderate size |
  | Best quality | `/prepress` | 300 dpi | Largest file, best quality |

- Compression runs in a background thread, and the UI polls for progress.
- Uploads are sanitized and temporary files are deleted after download.

## Requirements

- Python 3.9+
- [Ghostscript](https://ghostscript.com/releases/gsdnld.html), with `gswin64c` (Windows) or `gs` (Linux/macOS) on your `PATH`

## Setup

```bash
git clone https://github.com/aqilown/COMPRESSION.IO.git
cd PDFCOMPRESSOR
python -m venv .venv
.venv\Scripts\activate        # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
python app.py
```

Open http://127.0.0.1:5000.

## API

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/compress-pdf` | Form fields: `files` (one or more PDFs) and `quality` (`/screen`, `/ebook`, `/printer` or `/prepress`). Returns `{task_id}`. |
| GET | `/api/compress-status/<task_id>` | Returns `{status: processing\|done\|error, error}`. |
| GET | `/api/compress-download/<task_id>` | Downloads the result. The task is deleted after the download. |

## Project structure

```
PDFCOMPRESSOR/
├── app.py              # Flask app and Ghostscript wrapper
├── requirements.txt
└── templates/
    └── index.html      # Frontend UI
```

## Known limitations

- Task state is held in memory, so it only works with a single process. Use a proper job queue for multi-worker deployments.
- There is no upload size limit.
- `debug=True` is on. Turn it off before deploying.
- The UI loads Tailwind from the CDN.

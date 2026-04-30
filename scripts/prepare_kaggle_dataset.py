"""Package the v0.2 instruction dataset for upload as a Kaggle dataset.

Creates ``kaggle_upload/`` with:
- ``instruction_dataset_v0.2.jsonl`` (copy of the source)
- ``dataset-metadata.json`` (Kaggle's required schema)
- ``README.md`` (auto-generated description with row count + sha256)

Output is ready for ``kaggle datasets create -p kaggle_upload`` once
the ``kaggle`` CLI is configured. This script does NOT upload — it
only prepares the directory.

The kaggle_upload/ directory is gitignored. Re-run this script
whenever the source dataset changes (a new vN.M.jsonl is produced).

Stdlib only — safe to import anywhere.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import shutil
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = _PROJECT_ROOT / "data" / "processed" / "instruction_dataset_v0.2.jsonl"
DEFAULT_OUTPUT_DIR = _PROJECT_ROOT / "kaggle_upload"
DEFAULT_SLUG = "indiccrimlawllm-instruction-v02"
DEFAULT_TITLE = "IndicCrimLawLLM instruction dataset v0.2"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    p.add_argument("--slug", type=str, default=DEFAULT_SLUG)
    p.add_argument("--title", type=str, default=DEFAULT_TITLE)
    p.add_argument(
        "--owner",
        type=str,
        default="REPLACE_WITH_KAGGLE_USERNAME",
        help="Kaggle username; substituted into the dataset-metadata.json `id` field.",
    )
    return p.parse_args(argv)


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _line_count(path: Path) -> int:
    n = 0
    with path.open("rb") as f:
        for _ in f:
            n += 1
    return n


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
    )
    log = logging.getLogger("prepare_kaggle_dataset")

    source = Path(args.source).resolve()
    out_dir = Path(args.output_dir).resolve()

    if not source.exists():
        log.error("Source dataset not found: %s", source)
        return 1

    if out_dir.exists():
        log.info("Removing existing %s", out_dir)
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    dest = out_dir / source.name
    shutil.copy2(source, dest)
    log.info("Copied %s -> %s", source.name, dest)

    sha = _file_sha256(source)
    n_lines = _line_count(source)
    size_bytes = source.stat().st_size
    log.info(
        "Dataset: %d rows, %s bytes, sha256=%s...",
        n_lines, f"{size_bytes:,}", sha[:12],
    )

    metadata = {
        "title": args.title,
        "id": f"{args.owner}/{args.slug}",
        "licenses": [{"name": "CC0-1.0"}],
        "resources": [
            {
                "path": source.name,
                "description": (
                    "Alpaca-style instruction dataset for IPC/BNS/CrPC/BNSS "
                    "criminal law fine-tuning."
                ),
            }
        ],
    }
    (out_dir / "dataset-metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )

    readme = (
        f"# {args.title}\n\n"
        f"Alpaca-style instruction dataset for fine-tuning Indian criminal law LLMs.\n\n"
        f"- **Records:** {n_lines}\n"
        f"- **Size:** {size_bytes:,} bytes\n"
        f"- **SHA-256:** `{sha}`\n\n"
        f"## Schema\n\n"
        f"Each line is one JSON object:\n\n"
        f"```json\n"
        f'{{"instruction": "...", "input": "", "output": "...", '
        f'"_metadata": {{"source": "...", "source_id": "...", '
        f'"generated_by": "...", "validated": false}}}}\n'
        f"```\n\n"
        f"## Generators\n\n"
        f"- `mapping_qa` — IPC<->BNS and CrPC<->BNSS section-mapping Q&A pairs.\n"
        f"- `section_interpretation` — top-cited IPC and CrPC section interpretation pairs.\n"
        f"- `refusal` — out-of-scope and hallucination-bait refusal pairs.\n"
        f"- `bns_transition` — Q&A pairs grounded in `docs/bns_transition_findings.md`.\n\n"
        f"## License\n\nCC0-1.0.\n"
    )
    (out_dir / "README.md").write_text(readme, encoding="utf-8")

    log.info("Output directory: %s", out_dir)
    for p in sorted(out_dir.iterdir()):
        log.info("  %s (%s bytes)", p.name, f"{p.stat().st_size:,}")

    log.info("")
    log.info("Next step (when ready to upload):")
    log.info("  1. Edit dataset-metadata.json `id` field with your Kaggle username.")
    log.info("  2. kaggle datasets create -p %s", out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())

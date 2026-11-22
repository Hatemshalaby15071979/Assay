#!/usr/bin/env python3
"""
Assay — Fuzzing corpus builder

This script creates the seed corpus for DOCX/XLSX fuzzing.
It is intended to be run locally before enabling CI fuzzing jobs.

Usage:
    python tooling/fuzz/corpora.py  # Creates seed corpus from examples/
"""

from pathlib import Path
import zipfile
import shutil

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent

def create_minimal_docx():
    """Create a minimal valid DOCX file for fuzzing corpus."""
    corpus_dir = PROJECT_ROOT / "tooling" / "fuzz" / "corpus" / "docx"
    corpus_dir.mkdir(parents=True, exist_ok=True)

    # Use existing example if available
    example_docs = list((PROJECT_ROOT / "examples").glob("*.docx"))

    if example_docs:
        dest = corpus_dir / "template.docx"
        shutil.copy(example_docs[0], dest)
        print(f"Copied {example_docs[0]} -> {dest}")

    # Create a minimal DOCX skeleton (would need actual implementation)
    # For now, this is a placeholder for pre-stable work
    print("Note: Full corpus generation requires additional tooling")

def create_minimal_xlsx():
    """Create minimal XLSX files for fuzzing corpus."""
    corpus_dir = PROJECT_ROOT / "tooling" / "fuzz" / "corpus" / "xlsx"
    corpus_dir.mkdir(parents=True, exist_ok=True)

    # Reference existing examples
    example_xlsx = list((PROJECT_ROOT / "examples").glob("*.xlsx"))

    for i, xlsx in enumerate(example_xlsx, 1):
        dest = corpus_dir / f"sample_{i}.xlsx"
        shutil.copy(xlsx, dest)
        print(f"Copied {xlsx} -> {dest}")

    # Note: In practice, would also create synthetic minimal files
    # with varying sheet counts, column counts, etc.
    print(f"Seed corpus created with {len(example_xlsx)} sample files")

if __name__ == "__main__":
    print("Building fuzzing corpus for Assay...")
    print()
    print("This is pre-shipment infrastructure. Run locally before stable release.")
    print()
    create_minimal_xlsx()
    create_minimal_docx()
    print()
    print("Corpus ready. Next steps:")
    print("  1. Implement harness.py with python-afl or libflame")
    print("  2. Add CI job for nightly fuzzing")
    print("  3. Set up crash triage workflow")
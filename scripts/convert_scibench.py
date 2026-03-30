#!/usr/bin/env python3
"""
Convert SciBench thermo/chemistry problems into cheme-evals fixture format.

Usage:
    python scripts/convert_scibench.py /tmp/scibench/dataset/original/thermo.json --indices 21,31,38,39
    python scripts/convert_scibench.py /tmp/scibench/dataset/original/atkins.json --indices 0,1,5

Outputs fixture JSON files to fixtures/ directory.
"""

import json
import re
import sys
import argparse
from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def clean_latex(text: str) -> str:
    """Convert LaTeX markup to readable plain text, preserving math meaning."""
    # Remove \mathrm{}, \text{}, \operatorname{} wrappers but keep content
    text = re.sub(r'\\mathrm\{~?([^}]*)\}', r'\1', text)
    text = re.sub(r'\\text\{~?([^}]*)\}', r'\1', text)
    text = re.sub(r'\\operatorname\{([^}]*)\}', r'\1', text)
    # Superscripts/subscripts to readable form
    text = re.sub(r'\^\{(-?\d+)\}', r'^\1', text)        # ^{-1} → ^-1
    text = re.sub(r'_\{([^}]*)\}', r'_\1', text)         # _{benzene} → _benzene
    # Common LaTeX commands
    text = text.replace('\\rightarrow', '→')
    text = text.replace('\\rightleftharpoons', '⇌')
    text = text.replace('\\times', '×')
    text = text.replace('\\cdot', '·')
    text = text.replace('\\Delta', 'Δ')
    text = text.replace('\\mu', 'μ')
    text = text.replace('\\circ', '°')
    text = text.replace('\\left(', '(')
    text = text.replace('\\right)', ')')
    text = text.replace('\\left[', '[')
    text = text.replace('\\right]', ']')
    # Remove $ math delimiters
    text = text.replace('$', '')
    # Remove empty braces from spacing commands like ${ }^6$
    text = re.sub(r'\{\s*\}', '', text)
    # Remove remaining backslash-space commands like \, \; \~
    text = re.sub(r'\\[,;~! ]', ' ', text)
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def parse_unit(raw_unit: str) -> str:
    """Normalize SciBench unit strings."""
    cleaned = clean_latex(raw_unit).strip()
    # Common normalizations
    replacements = {
        'atm': 'atm',
        'bar': 'bar',
        'K': 'K',
        'J': 'J',
        'kJ': 'kJ',
        'Torr': 'Torr',
        'Pa': 'Pa',
        'L': 'L',
        '%': '%',
    }
    for k, v in replacements.items():
        if k in cleaned:
            return v
    return cleaned if cleaned else 'dimensionless'


def convert_problem(problem: dict, source_name: str, index: int) -> dict:
    """
    Convert a single SciBench problem into a cheme-evals fixture SKELETON.

    The output is intentionally incomplete — it needs human review to add:
    - Properly parsed inputs (from problem text)
    - Tolerance rationale
    - Reasoning checkpoints
    - Common mistakes
    - Physical constraints

    This is a starting point, not a finished fixture.
    """
    pid = problem['problemid'].strip().replace(' ', '-')
    fixture_id = f"scibench-{source_name}-{pid}"

    # Clean up problem text — convert LaTeX to readable plain text
    problem_text = clean_latex(problem['problem_text'].strip())

    # Parse answer
    answer_val = problem['answer_number']
    if isinstance(answer_val, str):
        answer_val = float(answer_val.replace('+', ''))
    raw_unit = problem.get('unit', '')
    unit = parse_unit(raw_unit)

    fixture = {
        "id": fixture_id,
        "version": "0.1.0",
        "_status": "DRAFT — requires human review of inputs, tolerances, and checkpoints",
        "tags": ["scibench", source_name],
        "source": {
            "type": "textbook",
            "reference": f"SciBench dataset, source: {source_name}, problem {pid}",
            "verified_by": "scibench_dataset"
        },
        "problem": {
            "statement": problem_text,
            "task": f"Calculate the answer and express in {unit}.",
            "difficulty": "intermediate",
            "topics": [source_name]
        },
        "inputs": {
            "_TODO": {
                "value": "PARSE_FROM_PROBLEM_TEXT",
                "unit": "TODO",
                "description": "Extract structured inputs from the problem statement above"
            }
        },
        "expected_outputs": {
            "answer": {
                "value": answer_val,
                "unit": unit,
                "description": f"Expected answer from SciBench (raw unit: {raw_unit.strip()})"
            }
        },
        "acceptance_criteria": {
            "tolerances": {
                "answer": {
                    "type": "relative_percent",
                    "value": 5.0,
                    "_comment": "TODO — set appropriate tolerance based on problem type"
                }
            },
            "must_include": [],
            "must_not_include": []
        },
        "domain_context": {
            "recommended_tools": [],
            "key_assumptions": [],
            "common_mistakes": []
        },
        "agent_evaluation": {
            "reasoning_checkpoints": [],
            "skill_document_expected": False
        }
    }

    # If solution is available, include it as a reference
    if problem.get('solution'):
        fixture["_reference_solution"] = problem['solution']

    return fixture


def main():
    parser = argparse.ArgumentParser(description="Convert SciBench problems to cheme-evals fixtures")
    parser.add_argument("source_file", help="Path to SciBench JSON file (e.g., thermo.json)")
    parser.add_argument("--indices", type=str, required=True,
                        help="Comma-separated problem indices to convert")
    parser.add_argument("--outdir", type=str, default=str(FIXTURES_DIR),
                        help="Output directory for fixtures")
    args = parser.parse_args()

    indices = [int(i) for i in args.indices.split(",")]
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    # Determine source name from filename
    source_path = Path(args.source_file)
    source_name = source_path.stem.replace('_sol', '')

    # Load problems
    with open(args.source_file) as f:
        problems = json.load(f)

    # Try to load solutions if available
    sol_path = source_path.parent / f"{source_name}_sol.json"
    sol_map = {}
    if sol_path.exists():
        with open(sol_path) as f:
            sols = json.load(f)
        sol_map = {s['problemid'].strip(): s for s in sols}

    converted = 0
    for idx in indices:
        if idx >= len(problems):
            print(f"  SKIP: index {idx} out of range (max {len(problems) - 1})")
            continue

        p = problems[idx]
        pid = p['problemid'].strip()

        # Merge solution if available
        if pid in sol_map:
            p['solution'] = sol_map[pid]['solution']

        fixture = convert_problem(p, source_name, idx)
        out_path = outdir / f"{fixture['id']}.json"

        # Guard: never overwrite a fixture that has been promoted past draft
        if out_path.exists():
            with open(out_path) as existing_f:
                existing = json.load(existing_f)
            existing_version = existing.get("version", "0.0.0")
            if not existing_version.startswith("0."):
                print(f"  SKIP: {out_path.name} is version {existing_version} (curated) — will not overwrite")
                continue

        with open(out_path, 'w') as f:
            json.dump(fixture, f, indent=2)

        print(f"  CREATED: {out_path}")
        print(f"    Problem: {p['problem_text'][:80]}...")
        print(f"    Answer:  {p['answer_number']} {p.get('unit', '')}")
        print(f"    STATUS:  DRAFT — needs human review")
        converted += 1

    print(f"\nConverted {converted} problems. All marked as DRAFT.")
    print("Next steps: review each fixture, parse inputs from problem text,")
    print("set tolerances, add reasoning checkpoints, and remove _TODO fields.")


if __name__ == "__main__":
    main()

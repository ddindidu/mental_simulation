"""Create a sex- and age-stratified persona CSV from Nemotron-Personas-USA.

The source CSV is streamed once, so the full ~1M-row dataset is never loaded
into memory. Sampling uses an independent reservoir for each of ten strata:

    Female/Male x (18-29, 30-39, 40-49, 50-59, 60+)

For any requested sample size, age-band totals and sex totals differ by at
most one. The output is ordered in a balanced round-robin sequence so that a
later step can assign consecutive rows to profiles without clustering one sex
or age band.

Examples:
    python 02_sampling_persona.py 345
    python 02_sampling_persona.py 345 --seed 42
    python 02_sampling_persona.py 345 --output sampled_personas.csv
"""

from __future__ import annotations

import argparse
import csv
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import TypeAlias

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT_PATH = SCRIPT_DIR / "nvidia_persona_filtered.csv"
DEFAULT_SEED = 42

SEXES = ("Female", "Male")
AGE_BANDS = (
    ("18-29", 18, 29),
    ("30-39", 30, 39),
    ("40-49", 40, 49),
    ("50-59", 50, 59),
    ("60+", 60, None),
)

# Keep the existing persona inputs and add non-occupational life contexts.
# List-valued columns remain serialized strings in CSV and can be normalized
# when the sampled rows are later converted to JSON.
OUTPUT_COLUMNS = (
    "uuid",
    "sex",
    "age",
    "marital_status",
    "education_level",
    "occupation",
    "persona",
    "professional_persona",
    "cultural_background",
    "hobbies_and_interests",
    "sports_persona",
    "arts_persona",
    "travel_persona",
    "culinary_persona",
)

Stratum: TypeAlias = tuple[str, str]


def age_band(age: int) -> str | None:
    """Return the configured adult age band, or None for minors."""
    for label, minimum, maximum in AGE_BANDS:
        if age >= minimum and (maximum is None or age <= maximum):
            return label
    return None


def build_allocation_order(sample_size: int) -> list[Stratum]:
    """Build a maximally balanced sex-by-age allocation for ``sample_size``.

    Five age bands and two sexes are coprime cycles, so every block of ten
    positions visits each cross-stratum exactly once. Any remainder is spread
    across different age bands and alternates sex.
    """
    if sample_size <= 0:
        raise ValueError(f"sample_size must be positive, got {sample_size}")

    band_labels = [label for label, _, _ in AGE_BANDS]
    return [
        (SEXES[index % len(SEXES)], band_labels[index % len(band_labels)])
        for index in range(sample_size)
    ]


def stratum_targets(allocation_order: list[Stratum]) -> Counter[Stratum]:
    return Counter(allocation_order)


def validate_columns(fieldnames: list[str] | None, input_path: Path) -> None:
    if not fieldnames:
        raise ValueError(f"{input_path} has no CSV header")

    missing = [column for column in OUTPUT_COLUMNS if column not in fieldnames]
    if missing:
        raise ValueError(
            f"{input_path.name} is missing required output columns: {', '.join(missing)}"
        )


def stratified_reservoir_sample(
    input_path: Path,
    targets: Counter[Stratum],
    rng: random.Random,
) -> tuple[dict[Stratum, list[dict[str, str]]], Counter[Stratum], Counter[str]]:
    """Uniformly sample the requested number of rows within every stratum."""
    reservoirs: dict[Stratum, list[dict[str, str]]] = defaultdict(list)
    seen: Counter[Stratum] = Counter()
    skipped: Counter[str] = Counter()

    with input_path.open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        validate_columns(reader.fieldnames, input_path)

        for row in reader:
            sex = (row.get("sex") or "").strip()
            if sex not in SEXES:
                skipped["unsupported_sex"] += 1
                continue

            try:
                age = int(row["age"])
            except (KeyError, TypeError, ValueError):
                skipped["invalid_age"] += 1
                continue

            band = age_band(age)
            if band is None:
                skipped["under_18"] += 1
                continue

            stratum = (sex, band)
            target = targets[stratum]
            if target == 0:
                continue

            seen[stratum] += 1
            reservoir = reservoirs[stratum]
            if len(reservoir) < target:
                reservoir.append(row)
                continue

            replacement_index = rng.randrange(seen[stratum])
            if replacement_index < target:
                reservoir[replacement_index] = row

    deficits = {
        stratum: target - len(reservoirs[stratum])
        for stratum, target in targets.items()
        if len(reservoirs[stratum]) < target
    }
    if deficits:
        detail = ", ".join(
            f"{sex}/{band}: need {targets[(sex, band)]}, found {seen[(sex, band)]}"
            for sex, band in sorted(deficits)
        )
        raise ValueError(f"Not enough eligible source rows for requested strata: {detail}")

    return dict(reservoirs), seen, skipped


def order_sampled_rows(
    reservoirs: dict[Stratum, list[dict[str, str]]],
    allocation_order: list[Stratum],
    rng: random.Random,
) -> list[dict[str, str]]:
    """Arrange sampled rows according to the balanced allocation order."""
    for rows in reservoirs.values():
        rng.shuffle(rows)

    cursors: Counter[Stratum] = Counter()
    ordered_rows: list[dict[str, str]] = []
    for stratum in allocation_order:
        ordered_rows.append(reservoirs[stratum][cursors[stratum]])
        cursors[stratum] += 1
    return ordered_rows


def write_sample(output_path: Path, rows: list[dict[str, str]]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as destination:
        writer = csv.DictWriter(destination, fieldnames=OUTPUT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in OUTPUT_COLUMNS})


def print_summary(
    sample_size: int,
    targets: Counter[Stratum],
    seen: Counter[Stratum],
    skipped: Counter[str],
    output_path: Path,
    seed: int,
) -> None:
    print(f"Sample size: {sample_size}")
    print(f"Seed: {seed}")
    print("\nTarget allocation:")
    print(f"{'Age band':<10} {'Female':>8} {'Male':>8} {'Total':>8}")
    for band, _, _ in AGE_BANDS:
        female = targets[("Female", band)]
        male = targets[("Male", band)]
        print(f"{band:<10} {female:>8} {male:>8} {female + male:>8}")

    female_total = sum(targets[("Female", band)] for band, _, _ in AGE_BANDS)
    male_total = sum(targets[("Male", band)] for band, _, _ in AGE_BANDS)
    print(f"{'Total':<10} {female_total:>8} {male_total:>8} {sample_size:>8}")

    print("\nEligible source rows by stratum:")
    for band, _, _ in AGE_BANDS:
        print(
            f"{band:<10} Female={seen[('Female', band)]:>7} "
            f"Male={seen[('Male', band)]:>7}"
        )

    if skipped:
        skipped_text = ", ".join(f"{reason}={count}" for reason, count in sorted(skipped.items()))
        print(f"\nSkipped source rows: {skipped_text}")
    print(f"\nWrote {sample_size} personas -> {output_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("n", type=int, help="Total number of personas to sample.")
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT_PATH,
        help=f"Source Nemotron persona CSV (default: {DEFAULT_INPUT_PATH.name}).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output CSV path (default: sampled_personas_n<N>_seed<SEED>.csv beside this script).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help=f"Random seed for reproducible sampling (default: {DEFAULT_SEED}).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.n <= 0:
        raise SystemExit(f"n must be positive, got {args.n}")
    if not args.input.is_file():
        raise SystemExit(f"Input CSV does not exist: {args.input}")

    output_path = args.output or SCRIPT_DIR / f"sampled_personas_n{args.n}_seed{args.seed}.csv"
    rng = random.Random(args.seed)

    allocation_order = build_allocation_order(args.n)
    targets = stratum_targets(allocation_order)
    reservoirs, seen, skipped = stratified_reservoir_sample(args.input, targets, rng)
    sampled_rows = order_sampled_rows(reservoirs, allocation_order, rng)

    if len({row["uuid"] for row in sampled_rows}) != args.n:
        raise ValueError("Sampled rows contain duplicate UUIDs")

    write_sample(output_path, sampled_rows)
    print_summary(args.n, targets, seen, skipped, output_path, args.seed)


if __name__ == "__main__":
    main()

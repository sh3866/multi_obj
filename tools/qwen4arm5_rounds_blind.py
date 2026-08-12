#!/usr/bin/env python3
"""Build/validate/unblind an anonymous packet for every unique R0-R5 artifact."""
import argparse
import json
import secrets
import shutil
from pathlib import Path

ROOT = Path("results_b200/qwen4arm5_qwen36_27b")
ARMS = ("SELF", "FUSED", "AXES", "MAD")
OUT = ROOT / "rounds_blind"


def make() -> None:
    packet = OUT / "packet"
    packet.mkdir(parents=True, exist_ok=False)
    tasks = json.loads(
        Path("results_b200/gold12_qwen36_27b/protocol/tasks.json").read_text()
    )
    key, manifest = {}, []
    for task_row in tasks:
        task = task_row["app"]
        task_dir = packet / task
        task_dir.mkdir()
        codes = []

        # The R0 HTML is shared, but each arm was rendered independently and can
        # differ due to animation timing. Keep every observed R0 for trajectories.
        for arm in ARMS:
            for round_idx in range(0, 6):
                source = ROOT / arm / "problems" / task / "candidates" / f"r{round_idx}.png"
                if not source.exists():
                    raise FileNotFoundError(source)
                code = secrets.token_hex(8)
                shutil.copyfile(source, task_dir / f"{code}.png")
                key[f"{task}/{code}"] = {"arm": arm, "round": round_idx}
                codes.append(code)

        # Random identifiers reveal neither method nor chronology; shuffle presentation too.
        secrets.SystemRandom().shuffle(codes)
        manifest.append({"task": task, "brief": task_row["instruction"], "codes": codes})

    (OUT / "key.json").write_text(json.dumps(key, indent=2))
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"created {len(key)} anonymous unique artifacts")


def validate(score_name: str) -> None:
    manifest = json.loads((OUT / "manifest.json").read_text())
    scores = json.loads((OUT / score_name).read_text())
    expected = {(row["task"], code) for row in manifest for code in row["codes"]}
    observed = [(row["task"], row["code"]) for row in scores]
    if len(observed) != len(set(observed)):
        raise RuntimeError("duplicate task/code rows")
    if set(observed) != expected:
        raise RuntimeError(f"manifest mismatch: missing={expected-set(observed)}, extra={set(observed)-expected}")
    fields = ("layout_hierarchy", "spacing_alignment_balance", "color_typography",
              "style_originality_finish", "overall")
    for row in scores:
        for field in fields:
            if type(row.get(field)) is not int or not 1 <= row[field] <= 10:
                raise RuntimeError(f"invalid {field}: {row}")
        if not isinstance(row.get("reason"), str) or not row["reason"].strip():
            raise RuntimeError(f"missing reason: {row}")
    print(f"validated {len(scores)} locked blind judgments")


def unblind(score_name: str, output_name: str) -> None:
    validate(score_name)
    key = json.loads((OUT / "key.json").read_text())
    scores = json.loads((OUT / score_name).read_text())
    for row in scores:
        row.update(key[f'{row["task"]}/{row["code"]}'])
    (OUT / output_name).write_text(json.dumps(scores, ensure_ascii=False, indent=2))
    print(f"unblinded {len(scores)} locked judgments")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("make", "validate", "unblind"))
    parser.add_argument("--scores", default="independent_gpt56_scores_blind.json")
    parser.add_argument("--output", default="independent_gpt56_scores_unblinded.json")
    args = parser.parse_args()
    if args.stage == "make":
        make()
    elif args.stage == "validate":
        validate(args.scores)
    else:
        unblind(args.scores, args.output)

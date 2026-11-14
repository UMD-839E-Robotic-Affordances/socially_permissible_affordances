import argparse
import json
import sys
from pathlib import Path
from types import SimpleNamespace

# Make `llm` and `scenarios` importable when run as a script from anywhere:
#   python rq1/rq1_experiment.py
ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "rq1")]

from tqdm import tqdm
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score

from llm import LLMOutputError, LLMProvider

# One stateful provider reused for every call. Default "mock" needs no API key.
#   python rq1/rq1_experiment.py --model claude-haiku-5-5 --effort low
ap = argparse.ArgumentParser()
ap.add_argument("--model", default="mock")
ap.add_argument("--effort", default=None)
ap.add_argument("--tag", default=None, help="suffix for the results file name, e.g. a commit hash")
args = ap.parse_args()
llm = LLMProvider(args.model, effort=args.effort)


def ask(text):
    """Judgment string, or "invalid" (with a warning) if the model's output can't be parsed."""
    try:
        return llm.call(text).judgment
    except LLMOutputError as e:
        tqdm.write(f"WARNING: invalid model output: {e}")
        return "invalid"


with open(ROOT / "dataset.json", encoding="utf-8") as f:
    scenario_list = [SimpleNamespace(**d) for d in json.load(f)]

current_dir = Path(__file__).resolve().parent

# 2. Go up one level to the root directory, then point to the JSON file
json_path = current_dir.parent / "dataset_review" / "categories.json"

# Fields meant only for human reviewers are removed so they never reach the model.
REVIEWER_ONLY = ("reviewer_notes",)
with open(json_path, "r", encoding="utf-8") as file:
    _cats = json.load(file)
for _meta in _cats["categories"].values():
    for _k in REVIEWER_ONLY:
        _meta.pop(_k, None)
taxonomy = json.dumps(_cats, indent=2, ensure_ascii=False)

has_tax_text = "Here is a taxonomy of decision parameters to determine your action. "
has_ex_text = "Here are some example scenarios and judgements. "

# Few-shot examples come from the dataset itself (single source of truth). These
# scenarios are excluded from scoring for every prompt type.
EXAMPLE_IDS = ("S001", "S003", "S004")


def format_example(n, sc):
    return (f"Example {n}: Scenario: {sc.context} Goal: {sc.goal}. Action: {sc.action}. "
            f"Relevant Object: {sc.object}. Judgement: {sc.judgment.capitalize()}. "
            f"Taxonomy: {', '.join(sc.tags)}. Reasoning: {sc.summary.rstrip('.')}.")


by_id = {sc.id: sc for sc in scenario_list}
examples = "\n".join(format_example(n, by_id[i]) for n, i in enumerate(EXAMPLE_IDS, 1))

# What each prompt type contains. Saved in the results JSON so a results file is
# self-describing (the meaning of a type name has changed before).
PROMPT_PARTS = {
    "none": [],
    "taxonomy": ["taxonomy"],
    "examples": ["examples"],
    "tax+ex": ["taxonomy", "examples"],
}
prompt_types = list(PROMPT_PARTS)
PART_TEXT = {"taxonomy": has_tax_text.strip() + "\n" + taxonomy, "examples": has_ex_text.strip() + "\n" + examples}


def build_prompt(scenario_text, prompt_type):
    """Background parts first (taxonomy, examples), blank-line separated; the scenario to judge comes last."""
    parts = [PART_TEXT[p] for p in PROMPT_PARTS[prompt_type]]
    return "\n\n".join(parts + [scenario_text])


results = {}

for scenario in tqdm(scenario_list, desc=args.model, unit="scenario"):
    # Few-shot examples are skipped for EVERY prompt type so all types are scored
    # on the same scenarios.
    if scenario.id in EXAMPLE_IDS:
        continue
    results[scenario.id] = {}
    scenario_text = f"Scenario: {scenario.context} Goal: {scenario.goal}. Action: {scenario.action}. Relevant Object: {scenario.object}."
    for prompt_type in prompt_types:
        prompt = build_prompt(scenario_text, prompt_type)
        answer = ask(prompt)
        results[scenario.id][prompt_type] = {
            "answer": str(answer),
            "correct": (answer == scenario.judgment),
            "prompt_chars": len(prompt),  # for later length-vs-accuracy analysis
        }


results_dir = ROOT / "rq1" / "results"
results_dir.mkdir(exist_ok=True)
tag = args.model + (f"_{args.effort}" if args.effort else "") + (f"_{args.tag}" if args.tag else "")
output_file = results_dir / f"rq1_results_{tag}.json"
config = {"provider": llm.provider, "model": llm.model, "effort": llm.effort, "thinking": llm.thinking,
          "max_tokens": llm.max_tokens, "prompt_types": prompt_types, "prompt_parts": PROMPT_PARTS,
          "n_scenarios": len(results)}
with open(output_file, "w") as f:
    json.dump({"config": config, "results": results}, f, indent=4)

print("\n--- PERFORMANCE COMPARISON ---")
print(f"{'Experiment Type':<18} | {'Accuracy':<8} | {'Balanced Acc':<12} | {'F1-Macro':<8}")
print("-" * 60)

for current_type in prompt_types:
    y_true = []
    y_pred = []
    
    # Reconstruct the true labels and predictions for this specific experiment type
    for scenario in scenario_list:
        if scenario.id not in results:  # skipped (used as few-shot examples)
            continue
        # Ground truth comes from the scenario object
        actual = scenario.judgment 
        # Prediction comes from your nested results dictionary
        predicted = results[scenario.id][current_type]["answer"]
        
        y_true.append(actual)
        y_pred.append(predicted)
        
    # Calculate performance metrics
    acc = accuracy_score(y_true, y_pred)
    bal_acc = balanced_accuracy_score(y_true, y_pred)
    f1 = f1_score(y_true, y_pred, average="macro", zero_division=0)
    
    # Print the formatted row
    print(f"{current_type:<18} | {acc:.4f}   | {bal_acc:.4f}       | {f1:.4f}")
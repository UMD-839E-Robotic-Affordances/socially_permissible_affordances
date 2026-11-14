import argparse
import json
import logging
import pprint
import sys
import time
from datetime import datetime
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
ap.add_argument("--limit", type=int, default=None, help="only score the first N scenarios (debugging)")
ap.add_argument("--log-file", default=None, help="DEBUG log path (default rq1/logs/rq1_<model>_<time>.log)")
args = ap.parse_args()

# --- Debug logging: every step and variable goes to a file at DEBUG level; the console shows only warnings. ---
log_dir = ROOT / "rq1" / "logs"
log_dir.mkdir(exist_ok=True)
log_path = Path(args.log_file) if args.log_file else log_dir / f"rq1_{args.model}_{datetime.now():%Y%m%d_%H%M%S}.log"
file_handler = logging.FileHandler(log_path, encoding="utf-8")
file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s:%(lineno)d  %(message)s"))
console = logging.StreamHandler()
console.setLevel(logging.WARNING)
# Only our own loggers are verbose; SDK/HTTP libraries stay at WARNING so request headers (API keys) are never logged.
logging.basicConfig(level=logging.WARNING, handlers=[file_handler, console])
logging.getLogger("rq1").setLevel(logging.DEBUG)
log = logging.getLogger("rq1.experiment")


def show(name, value):
    """Log a variable: its name, type and a pretty-printed value."""
    text = value if isinstance(value, str) else pprint.pformat(value, width=120, sort_dicts=False)
    log.debug("VAR %s  (%s)\n%s", name, type(value).__name__, text)


log.debug("=== STEP 1: arguments and provider ===")
show("args", vars(args))
show("log_path", str(log_path))
llm = LLMProvider(args.model, effort=args.effort)
show("llm settings", {"provider": llm.provider, "model": llm.model, "effort": llm.effort,
                      "thinking": llm.thinking, "max_tokens": llm.max_tokens})


def ask(text):
    """Judgment string, or "invalid" (with a warning) if the model's output can't be parsed."""
    try:
        return llm.call(text).judgment
    except LLMOutputError as e:
        log.warning("invalid model output: %s", e)
        tqdm.write(f"WARNING: invalid model output: {e}")
        return "invalid"


with open(ROOT / "dataset.json", encoding="utf-8") as f:
    scenario_list = [SimpleNamespace(**d) for d in json.load(f)]
log.debug("=== STEP 2: load dataset ===")
show("dataset path", str(ROOT / "dataset.json"))
show("n scenarios", len(scenario_list))
show("first scenario", vars(scenario_list[0]))

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
log.debug("=== STEP 3: taxonomy text ===")
show("categories.json path", str(json_path))
show("REVIEWER_ONLY (fields stripped)", REVIEWER_ONLY)
show("n categories", len(_cats["categories"]))
show("taxonomy text (%d chars)" % len(taxonomy), taxonomy)

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
log.debug("=== STEP 4: few-shot examples ===")
show("EXAMPLE_IDS (excluded from scoring)", EXAMPLE_IDS)
for _i in EXAMPLE_IDS:
    show(f"example source {_i}", vars(by_id[_i]))
show("examples text (%d chars)" % len(examples), examples)
=======
examples = "\n".join(format_example(n, by_id[i]) for n, i in enumerate(EXAMPLE_IDS, 1))
>>>>>>> rq1-prompt-metadata-analysis

# What each prompt type contains. Saved in the results JSON so a results file is
# self-describing (the meaning of a type name has changed before).
PROMPT_PARTS = {
    "none": [],
    "taxonomy": ["taxonomy"],
    "examples": ["examples"],
    "tax+ex": ["taxonomy", "examples"],
}
prompt_types = list(PROMPT_PARTS)
<<<<<<< HEAD
show("PROMPT_PARTS", PROMPT_PARTS)
show("has_tax_text", has_tax_text)
show("has_ex_text", has_ex_text)
PART_TEXT = {"taxonomy": has_tax_text.strip() + "\n" + taxonomy, "examples": has_ex_text.strip() + "\n" + examples}


def build_prompt(scenario_text, prompt_type):
    """Background parts first (taxonomy, examples), blank-line separated; the scenario to judge comes last."""
    parts = [PART_TEXT[p] for p in PROMPT_PARTS[prompt_type]]
    return "\n\n".join(parts + [scenario_text])


results = {}
log.debug("=== STEP 5: per-scenario loop ===")
to_score = [sc for sc in scenario_list if sc.id not in EXAMPLE_IDS]
if args.limit:
    to_score = to_score[: args.limit]
show("scenario ids to score", [sc.id for sc in to_score])

for scenario in tqdm(scenario_list, desc=args.model, unit="scenario"):
    # Few-shot examples are skipped for EVERY prompt type so all types are scored
    # on the same scenarios.
    if scenario.id in EXAMPLE_IDS:
        continue
    if args.limit and scenario not in to_score:
        continue
    log.debug("--- scenario %s ---", scenario.id)
    show("scenario", vars(scenario))
    results[scenario.id] = {}
    scenario_text = f"Scenario: {scenario.context} Goal: {scenario.goal}. Action: {scenario.action}. Relevant Object: {scenario.object}."
    show("scenario_text", scenario_text)
    show("expected judgment", scenario.judgment)
    for prompt_type in prompt_types:
        log.debug("... prompt_type=%s parts=%s", prompt_type, PROMPT_PARTS[prompt_type])
        prompt = build_prompt(scenario_text, prompt_type)
        show(f"prompt [{prompt_type}] ({len(prompt)} chars)", prompt)
        t0 = time.time()
        answer = ask(prompt)
        log.debug("answer=%r expected=%r correct=%s elapsed=%.2fs", answer, scenario.judgment,
                  answer == scenario.judgment, time.time() - t0)
        results[scenario.id][prompt_type] = {
            "answer": str(answer),
            "correct": (answer == scenario.judgment),
            "prompt_chars": len(prompt),  # for later length-vs-accuracy analysis
        }


log.debug("=== STEP 6: save results ===")
show("results", results)
# Debug (--limit) runs go to the logs dir so they never overwrite real results.
results_dir = log_dir if args.limit else ROOT / "rq1" / "results"
results_dir.mkdir(exist_ok=True)
tag = args.model + (f"_{args.effort}" if args.effort else "") + (f"_n{args.limit}" if args.limit else "")
output_file = results_dir / f"rq1_results_{tag}.json"
config = {"provider": llm.provider, "model": llm.model, "effort": llm.effort, "thinking": llm.thinking,
          "max_tokens": llm.max_tokens, "prompt_types": prompt_types, "prompt_parts": PROMPT_PARTS,
          "n_scenarios": len(results)}
with open(output_file, "w") as f:
    json.dump({"config": config, "results": results}, f, indent=4)
show("config", config)
show("output_file", str(output_file))
log.debug("=== STEP 7: metrics ===")

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
        
    show(f"y_true [{current_type}]", y_true)
    show(f"y_pred [{current_type}]", y_pred)
    # Calculate performance metrics
    acc = accuracy_score(y_true, y_pred)
    bal_acc = balanced_accuracy_score(y_true, y_pred)
    f1 = f1_score(y_true, y_pred, average="macro", zero_division=0)
    
    # Print the formatted row
    print(f"{current_type:<18} | {acc:.4f}   | {bal_acc:.4f}       | {f1:.4f}")
    log.debug("metrics [%s]: acc=%.4f bal_acc=%.4f f1_macro=%.4f", current_type, acc, bal_acc, f1)
log.debug("=== DONE ===")

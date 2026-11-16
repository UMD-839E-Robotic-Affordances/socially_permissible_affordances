import argparse
import json
import logging
import os
import random
import re
import signal
import sys
from pathlib import Path
from types import SimpleNamespace

# Make `llm` and `scenarios` importable when run as a script from anywhere:
#   python rq1/rq1_experiment.py
ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "rq1")]

from tqdm import tqdm
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score

from llm import LLMOutputError, LLMProvider, log_json

# One stateful provider reused for every call. Default "mock" needs no API key.
#   python rq1/rq1_experiment.py --model claude-haiku-5-5 --effort low
ap = argparse.ArgumentParser()
ap.add_argument("--model", default="mock")
ap.add_argument("--effort", default=None)
ap.add_argument("--tag", default=None, help="suffix for the results file name, e.g. a commit hash")
ap.add_argument("--web-search", action="store_true", help="give the model the web search tool (Claude only)")
ap.add_argument("--max-searches", type=int, default=3, help="max web searches per call (with --web-search)")
ap.add_argument("--ids", default=None, help="comma-separated scenario ids to score (e.g. a pilot subset)")
ap.add_argument("--why", action="store_true",
                help="after each judgment, ask a follow-up 'why' question in the same conversation")
ap.add_argument("--start-index", type=int, default=0,
                help="resume: skip the first N scenarios (dataset order) and keep the results already saved in the "
                     "output file (use the same --model/--effort/--tag/--seed as the interrupted run)")
ap.add_argument("--structured", action="store_true",
                help="Claude only: constrain the answer to a JSON schema ({\"judgment\": ...}), parsed with pydantic")
ap.add_argument("--log-file", default=None,
                help="DEBUG log of everything sent to and received from the model (default: rq1/logs/rq1_log_<name>.log)")
ap.add_argument("--no-log", action="store_true", help="turn the debug log off")
ap.add_argument("--overwrite", action="store_true",
                help="replace an existing results file with the same name (otherwise a fresh run refuses to start)")
ap.add_argument("--seed", type=int, default=42,
                help="seed for reproducible example selection")
args = ap.parse_args()
only_ids = set(args.ids.split(",")) if args.ids else None

# One descriptive name for this run's files. Every setting that changes the results is in it, so runs that differ never
# share a file; the scripts also add the git commit and a start time (--tag), so repeats do not either.
name_parts = [args.model] + ([args.effort] if args.effort else []) + [f"seed{args.seed}"]
if args.structured:
    name_parts.append("structured")
if not args.why:
    name_parts.append("nowhy")
if args.web_search:
    name_parts.append("web")
if only_ids:
    name_parts.append(f"subset{len(only_ids)}")
tag = "_".join(name_parts) + (f"_{args.tag}" if args.tag else "")
results_dir = ROOT / "rq1" / "results"  # never the deprecated/ subfolder
output_file = results_dir / f"rq1_results_{tag}.json"
why_file = results_dir / f"rq1_whys_{tag}.json"  # the follow-up "why" answers live here, not in the results file
log_dir = ROOT / "rq1" / "logs"
log_path = Path(args.log_file) if args.log_file else log_dir / f"rq1_log_{tag}.log"

if not args.no_log:  # only our own loggers are verbose; SDK/HTTP libraries stay quiet so request headers never reach the log
    log_path.parent.mkdir(parents=True, exist_ok=True)
    _h = logging.FileHandler(log_path, encoding="utf-8")  # append mode: a resumed run continues the same log
    _h.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s  %(message)s"))
    _rq = logging.getLogger("rq1")
    _rq.setLevel(logging.DEBUG)
    _rq.addHandler(_h)
    _rq.propagate = False
log = logging.getLogger("rq1.experiment")
log_json("RUN_ARGS", {**vars(args), "run_name": tag, "results_file": str(output_file), "whys_file": str(why_file)})
if not args.no_log:
    print(f"Debug log: {log_path}")
llm = LLMProvider(args.model, effort=args.effort, web_search=args.web_search, max_searches=args.max_searches,
                  structured=args.structured)


# Follow-up asked in the same conversation with --why. The same text is used for every prompt type, so
# differences in the stated factors come from the prompt, not from the question. The first sentence
# overrides the system prompt's one-word format for this reply only.
WHY_QUESTION = (
    "For this follow-up only, ignore the earlier output format. Why did you give that judgment? "
    'Reply with only a JSON object {"factors": [...], "reason": "..."}, where "factors" lists the one to '
    "three considerations that most influenced your judgment, each a short lowercase label of one or two "
    'words, and "reason" is one sentence.'
)


def parse_why(text):
    """The follow-up's JSON object, or None if it can't be parsed."""
    m = re.search(r"\{.*\}", text, re.DOTALL)
    try:
        d = json.loads(m.group(0)) if m else None
    except json.JSONDecodeError:
        return None
    return d if isinstance(d, dict) and isinstance(d.get("factors"), list) else None


def ask(text):
    """(judgment string, why dict or None). The judgment is "invalid" (with a warning) if unparseable."""
    try:
        if not args.why:
            return llm.call(text).judgment, None
        judgment, why_text = llm.call_with_why(text, WHY_QUESTION)
        return judgment.judgment, {"raw": why_text, "parsed": parse_why(why_text)}
    except LLMOutputError as e:
        tqdm.write(f"WARNING: invalid model output: {e}")
        return "invalid", None

def select_example(scenario, scenario_list, seed=42):
    candidates = [
        sc for sc in scenario_list
        if sc.id != scenario.id
        and sc.context != scenario.context  # never use a scenario's identical-context twin (it differs only in the answer)
        and set(sc.tags).intersection(scenario.tags)
    ]

    if not candidates:
        raise ValueError(
            f"No example found for scenario {scenario.id} "
            f"with tags {scenario.tags}"
        )

    rng = random.Random(f"{seed}:{scenario.id}")
    return rng.choice(candidates)


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
log_json("DATA", {"dataset_scenarios": len(scenario_list), "taxonomy_chars": len(taxonomy),
                  "reviewer_only_fields_stripped": list(REVIEWER_ONLY), "reviewer_notes_in_taxonomy": "reviewer_notes" in taxonomy})

has_tax_text = "Here is a taxonomy of decision parameters to determine your action. "
# Tells the model how to use the examples, which scenario to judge, and which output format to use.
has_ex_text = ("Below are examples of how to judge a scenario. Each shows the scenario, the correct response, "
               "and the reasoning behind it. They are for guidance only: do not judge them. Judge only the final "
               "scenario, which comes after the examples, and reply in the required output format (a single "
               "word or the JSON object), not in the format used in the examples.")
has_ex_nolabel_text = ("Below are examples of how to judge a scenario. Each shows the scenario and the correct "
                       "response. They are for guidance only: do not judge them. Judge only the final scenario, "
                       "which comes after the examples, and reply in the required output format (a single word "
                       "or the JSON object), not in the format used in the examples.")
final_text = "Now judge this scenario:"
# Closing instruction on EVERY prompt (not needed, and left out, in --structured mode, where the API enforces the format).
answer_format_text = None if args.structured else 'Reply with only one word: "accept", "reject" or "uncertain". Do not explain.'

# Each scenario gets one example drawn from the dataset itself (see select_example); every scenario is scored.


def format_example(n, sc, with_labels=True):
    """with_labels=False: just the scenario and the correct response; True also adds the reasoning (never the tags)."""
    text = (f"Example {n}: Scenario: {sc.context} Goal: {sc.goal}. Action: {sc.action}. "
            f"Relevant Object: {sc.object}. Correct response: {sc.judgment}.")
    if with_labels:
        summary = (sc.summary or "").rstrip(".")
        # No "Taxonomy:" tags here: the example is chosen because it shares a tag with the scenario being
        # judged, so showing its tags would reveal part of that scenario's gold category (label leak).
        if summary:
            text += f" Reasoning: {summary}."
    return text


# What each prompt type contains. Saved in the results JSON so a results file is
# self-describing (the meaning of a type name has changed before).
PROMPT_PARTS = {
    "none": [],
    "taxonomy": ["taxonomy"],
    "examples": ["examples"],
    "examples_nolabel": ["examples_nolabel"],  # same examples, only scenario + correct response
    "tax+ex": ["taxonomy", "examples"],
}
prompt_types = list(PROMPT_PARTS)
PART_TEXT = {
    "taxonomy": has_tax_text.strip() + "\n" + taxonomy,
}


def build_prompt(scenario_text, prompt_type, example=None):
    """Background parts first (taxonomy, examples), then the scenario to judge, introduced by final_text."""
    parts = []

    for p in PROMPT_PARTS[prompt_type]:
        if p == "taxonomy":
            parts.append(PART_TEXT["taxonomy"])

        elif p == "examples":
            if example is not None:
                example_text = format_example(1, example, with_labels=True)
                parts.append(has_ex_text.strip() + "\n" + example_text)

        elif p == "examples_nolabel":
            if example is not None:
                example_text = format_example(1, example, with_labels=False)
                parts.append(has_ex_nolabel_text.strip() + "\n" + example_text)

    tail = "\n\n" + answer_format_text if answer_format_text else ""
    if not parts:
        return scenario_text + tail

    return "\n\n".join(parts) + "\n\n" + final_text + "\n" + scenario_text + tail


results_dir.mkdir(exist_ok=True)
if args.start_index == 0 and not args.overwrite and (output_file.exists() or (args.why and why_file.exists())):
    sys.exit(f"Refusing to overwrite {output_file.name}: it already exists. Resume it with --start-index N, "
             f"use a different --tag, or pass --overwrite to replace it.")


def write_json(path, obj):
    """Atomic write, so an interrupted run never leaves a half-written file."""
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=4)
    os.replace(tmp, path)


results = {}
whys = {}  # scenario id -> prompt type -> {"raw", "parsed"}
selected_examples = {}
prev_usage = {}
if args.start_index > 0:
    if output_file.exists():
        with open(output_file, encoding="utf-8") as f:
            prev = json.load(f)
        results = prev["results"]
        selected_examples = prev["config"].get("selected_examples", {})
        prev_usage = prev["config"].get("usage", {})
        if why_file.exists():
            with open(why_file, encoding="utf-8") as f:
                whys = json.load(f)["whys"]
        print(f"Resuming: loaded {len(results)} finished scenarios from {output_file.name}")
        log_json("RESUME", {"loaded_scenarios": len(results), "start_index": args.start_index})
    else:
        print(f"WARNING: --start-index {args.start_index} but {output_file.name} does not exist; starting with no earlier results.")


def save(status, stopped_at=None):
    """Write the results file (and the whys file) with everything finished so far."""
    usage = {k: prev_usage.get(k, 0) + llm.usage[k] for k in llm.usage}
    config = {"provider": llm.provider, "model": llm.model, "effort": llm.effort, "thinking": llm.thinking,
              "max_tokens": llm.max_tokens, "web_search": llm.web_search,
              "max_searches": llm.max_searches if llm.web_search else None,
              "prompt_types": prompt_types, "prompt_parts": PROMPT_PARTS, "answer_format_text": answer_format_text, "structured": args.structured,
              "n_scenarios": len(results), "scenario_ids_filter": sorted(only_ids) if only_ids else None,
              "why_question": WHY_QUESTION if args.why else None,
              "why_file": why_file.name if args.why else None, "results_file": output_file.name,
              "log_file": None if args.no_log else str(log_path),
              "usage": usage, "seed": args.seed, "selected_examples": selected_examples,
              "status": status, "start_index": args.start_index, "stopped_at_index": stopped_at,
              "next_index": next_index}  # resume a stopped or killed run with --start-index <next_index>
    write_json(output_file, {"config": config, "results": results})
    log_json("SAVE", {"status": status, "scenarios": len(results), "file": str(output_file)})
    if args.why:
        write_json(why_file, {"config": {"model": llm.model, "effort": llm.effort, "seed": args.seed,
                                         "why_question": WHY_QUESTION, "results_file": output_file.name},
                              "whys": whys})
    return usage


index = args.start_index
next_index = args.start_index  # the --start-index to resume from: everything before it is saved


def _terminate(signum, frame):  # `kill`, tmux/terminal closing: stop like Ctrl-C so the run is saved and a resume hint is printed
    raise KeyboardInterrupt()


signal.signal(signal.SIGTERM, _terminate)
try:
    for index, scenario in enumerate(tqdm(scenario_list, desc=args.model, unit="scenario")):
        if index < args.start_index:
            continue
        if only_ids and scenario.id not in only_ids:
            next_index = index + 1
            continue
        if scenario.id in results and all(t in results[scenario.id] for t in prompt_types):
            next_index = index + 1
            continue  # already finished in the file we resumed from

        # Select one matching example from the entire dataset.
        example = select_example(scenario, scenario_list, seed=args.seed)

        entry, scenario_whys = {}, {}
        log_json("SCENARIO", {"index": index, "id": scenario.id, "context": scenario.context, "goal": scenario.goal,
                              "action": scenario.action, "object": scenario.object,
                              "gold_judgment (not sent to the model)": scenario.judgment, "tags (not sent)": scenario.tags,
                              "example_id": example.id, "example_judgment": example.judgment})
        scenario_text = f"Scenario: {scenario.context} Goal: {scenario.goal}. Action: {scenario.action}. Relevant Object: {scenario.object}."
        for prompt_type in prompt_types:
            prompt = build_prompt(scenario_text, prompt_type, example=example)
            log_json("PROMPT", {"scenario": scenario.id, "prompt_type": prompt_type, "chars": len(prompt), "prompt": prompt})
            before = dict(llm.usage)
            answer, why = ask(prompt)
            usage = {k: llm.usage[k] - before[k] for k in before}  # tokens for this prompt (judgment + why)
            log_json("RESULT", {"scenario": scenario.id, "prompt_type": prompt_type, "answer": answer, "gold": scenario.judgment,
                                "correct": answer == scenario.judgment, "why": why, "usage": usage})
            entry[prompt_type] = {
                "answer": str(answer),
                "correct": (answer == scenario.judgment),
                "prompt_chars": len(prompt),  # for later length-vs-accuracy analysis
                "usage": usage,
            }
            if why is not None:
                scenario_whys[prompt_type] = why
        # A scenario is stored only when all its prompt types are done, then the files are rewritten.
        results[scenario.id] = entry
        selected_examples[scenario.id] = example.id
        if scenario_whys:
            whys[scenario.id] = scenario_whys
        next_index = index + 1
        save("running")
except BaseException as e:
    save("stopped", stopped_at=index)
    tqdm.write(f"\nSTOPPED at scenario index {index} ({type(e).__name__}); {len(results)} scenarios are saved in {output_file}.")
    tqdm.write(f"Resume with the same arguments plus: --start-index {index}")
    raise

total = save("complete")
print(f"Results saved to {output_file}")
if args.why:
    print(f"Whys saved to {why_file}")
print(f"Token usage: {total}")

print("\n--- PERFORMANCE COMPARISON ---")
print(f"{'Experiment Type':<18} | {'Accuracy':<8} | {'Balanced Acc':<12} | {'F1-Macro':<8}")
print("-" * 60)

for current_type in prompt_types:
    y_true = []
    y_pred = []
    
    # Reconstruct the true labels and predictions for this specific experiment type
    for scenario in scenario_list:
        if scenario.id not in results:  # not scored in this run (--ids filter)
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
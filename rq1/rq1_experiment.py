import json
from . import llm
from .. import scenarios
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score
from pathlib import Path
# get scenarios list
# get taxonomy
# get examples?

# for each scenario:
#       for each in (no tax, tax, tax+examples)
#           Call LLM with scenario (context, goal, action, object) and extra info, along with model type and setings
#           Returns action, confirm it is one of three answers, print flag if not
#           Record to saved area: answer, does it match our answer

scenario_list = scenarios.SCENARIOS

current_dir = Path(__file__).resolve().parent

# 2. Go up one level to the root directory, then point to the JSON file
json_path = current_dir.parent / "categories.json"

with open(json_path, "r", encoding="utf-8") as file:
    taxonomy = file.read()

has_tax_text = "Here is a taxonomy of decision parameters to determine your action. "
has_ex_text = "Here are some example scenarios and judgements. "

examples = ""

types = ["no", "taxonomy", "examples"]

results = {}

for scenario in scenario_list:
    results[scenario.id] = {}
    scenario_text = f"Scenario: {scenario.context} Goal: {scenario.goal}. Action: {scenario.action}. Relevant Object: {scenario.object}."
    for type in types:
        if type == "no":
            answer = llm.mock_call(scenario_text)
        elif type == "taxonomy":
            answer = llm.mock_call(scenario_text+has_tax_text+taxonomy)
        elif type == "examples":
            answer = llm.mock_call(scenario_text+has_tax_text+taxonomy+has_ex_text+examples)
        answer = answer.judgment
        results[scenario.id][type] = {"answer": str(answer), "correct": (answer == scenario.judgment)}


output_file = "rq1_results.json"
with open(output_file, "w") as f:
    json.dump(results, f, indent=4)

print("\n--- PERFORMANCE COMPARISON ---")
print(f"{'Experiment Type':<18} | {'Accuracy':<8} | {'Balanced Acc':<12} | {'F1-Macro':<8}")
print("-" * 60)

for current_type in types:
    y_true = []
    y_pred = []
    
    # Reconstruct the true labels and predictions for this specific experiment type
    for scenario in scenario_list:
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
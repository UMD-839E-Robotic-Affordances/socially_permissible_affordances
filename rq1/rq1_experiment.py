import json
import llm
import scenarios
# get scenarios list
# get taxonomy
# get examples?

# for each scenario:
#       for each in (no tax, tax, tax+examples)
#           Call LLM with scenario (context, goal, action, object) and extra info, along with model type and setings
#           Returns action, confirm it is one of three answers, print flag if not
#           Record to saved area: answer, does it match our answer

scenario_list = scenarios.SCENARIOS
with open("data.json", "r", encoding="utf-8") as file:
    taxonomy = file.read()

examples = ""

types = ["no", "taxonomy", "examples"]

results = {}

for scenario in scenario_list:
    results[scenario.id] = {}
    scenario_text = f"Scenario: {scenario.context} Goal: {scenario.goal}. Action: {scenario.action}. Relevant Object: {scenario.object}."
    for type in types:
        if type == "no":
            answer = llm.mock_call(scenario_text, "")
        elif type == "taxonomy":
            answer = llm.mock_call(scenario_text, taxonomy)
        elif type == "examples":
            answer = llm.mock_call(scenario_text, taxonomy+examples)

        results[scenario.id][type] = {"answer": answer, "correct": (answer == scenario.judgment)}


output_file = "rq1_results.json"
with open(output_file, "w") as f:
    json.dump(results, f, indent=4)
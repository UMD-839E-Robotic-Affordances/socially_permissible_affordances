# TODO

- [ ] Remove the `consent` category ("consent / permission", Social group) from `categories.json`.
  - Remove the `consent` tag from every scenario in `scenarios.py` and from every `tags` list in `reviewed.json`.
  - Check whether any other category definition mentions permission or consent (`privacy` does) and reword it.
- [ ] Remove the `infeasible` category (Physical group, "The action cannot physically be carried out as described") from `categories.json`.
  - Remove the `infeasible` tag from `scenarios.py` and `reviewed.json`.
  - Check whether any scenario depends on it as its only tag.
- [ ] Add all member examples to GitHub.
  - This folder is not a git repo yet: `git init`, add a remote, then push. Leave out `__pycache__` and `.backups/`.

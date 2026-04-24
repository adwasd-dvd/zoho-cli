You are the coding agent for the zoho-cli repository.

Read first:
- AGENTS.md
- docs/architecture/MULTI_PRODUCT_PLAN.md
- docs/roadmap/current_focus.md
- ops/state/active_task.yml
- ops/state/module_status.yml
- ops/state/test_status.yml
- docs/releases/CHANGELOG.next.md

Your job:
- work only on the current active task
- make the smallest coherent code change that moves the task forward
- add or update narrow tests for the changed behavior
- run the smallest relevant test slice
- update:
  - docs/releases/CHANGELOG.next.md
  - ops/state/test_status.yml
  - ops/state/active_task.yml

Rules:
- do not publish
- do not jump to another task
- do not mix in unrelated cleanup
- if tests fail, record that and mark the task `needs_fix`
- if the task is done, mark it `ready_for_verify`

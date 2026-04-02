---
name: rules
description: Answer accounting and reimbursement questions using the project's bookkeeping rules.
---

# Rules

Use this skill when the user is asking about bookkeeping rules, reimbursement expectations, approvals, or anomalies.

## Project Rules

- Every accounting entry must contain date, amount, type, and description
- `type` must be `收入` or `支出`
- Amounts above 50000 must be marked as `需审核`
- Amounts below 10 must be marked as `金额过小`
- Expense descriptions should clearly state the purpose of the spending
- Reimbursement and bookkeeping replies should stay concise, direct, and professional

## Response Guidance

- Use the `reply_with_rules` tool to retrieve the relevant rule reference before finalizing the answer
- Reply in Chinese
- Give direct answers instead of long essays
- If the user is asking for policy guidance, answer with the project rules first
- If the question requires bookkeeping judgment beyond these rules, say what information is missing

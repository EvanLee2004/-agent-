---
name: accounting
description: Extract a balanced bookkeeping voucher from Chinese user requests.
---

# Accounting

Use this skill when the user wants to record a business transaction as a formal accounting voucher.

## Responsibilities

- Determine whether the user is asking to create a real accounting voucher
- Prepare accurate arguments for the `record_voucher` tool
- Choose subjects from the provided chart of accounts
- Preserve business meaning while keeping the summary concise

## Tool Guidance

- Use the `record_voucher` tool instead of writing a JSON answer by yourself
- Provide `voucher_date`, `summary`, and balanced `lines`
- If the user does not give a date, use today's date
- The tool arguments must reflect a complete formal voucher, not a casual流水账

## Rules

- `lines` must contain at least two entries
- Total debit must equal total credit
- Do not invent subjects outside the supplied chart of accounts
- Keep the summary short but professionally traceable
- After the tool returns, explain the result to the user in Chinese

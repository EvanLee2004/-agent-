---
name: audit
description: Extract structured voucher audit targets for deterministic review rules.
compatibility: opencode
---

# Audit

Use this skill when the user wants to review bookkeeping quality, audit vouchers, or inspect anomalies.

## Responsibilities

- Detect whether the user wants to review the latest voucher, all vouchers, or a specific voucher ID
- Call the `audit_voucher` tool with the right target arguments

## Tool Guidance

- Use `audit_voucher`
- Set `target` to `latest`, `all`, or `voucher_id`
- Only include `voucher_id` when the user explicitly points to a specific voucher

## Rules

- If the user says "latest", "刚才那笔", or similar, use `latest`
- If the user says "全部", use `all`
- If the user explicitly gives a voucher ID, use `voucher_id`
- Do not perform the audit by imagination; rely on the tool result
- After the tool returns, present the review result in concise Chinese

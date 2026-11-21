# API contract changelog

## 2026-11-20

- BREAKING CHANGE: CaptureLeadBody.associated_manufacturers and LeadOut.associated_manufacturers removed — a lead is exactly one manufacturer (company_name, max 120).
- Old-build compatibility for `POST /leads`: `name` and `company_name` are trimmed, and whitespace-only or under-2-character values are rejected (422). Names over 120 characters are rejected (422). An `associated_manufacturers` list sent by old builds is ignored; `company_name` is stored as the single manufacturer.

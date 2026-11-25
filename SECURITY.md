# Security policy

## Report a vulnerability

Report a vulnerability privately through
[GitHub private vulnerability reporting](https://github.com/reh3376/v2c-translator/security/advisories/new).
Do not open a public issue for it. Only the latest commit on `main` is supported.

## Never share a real service record

Do not attach a real DD-214, DD-215, VMET or other service record to an issue, a pull
request or an advisory, even a redacted one. The same applies to names, SSNs, DoD IDs,
dates of birth and addresses. To show a problem, use or adapt a synthetic fixture from
[`tests/fixtures/`](tests/fixtures/), which uses fictional names and placeholder IDs.

## What the tool keeps

`dd214kw` runs on your machine and sends nothing to a third-party service. From each
document it keeps branch, component, rank and pay grade, specialties and time in each,
service time, training and awards. It never captures the name, SSN or DoD ID, date of
birth, addresses, characterization of service, or separation and reentry codes. Free
text passes through a scrubber that redacts ID numbers, dates and contact details. See
[Privacy and responsible use](README.md#privacy-and-responsible-use).

This repository enforces the same rule: CI runs `scripts/pii_guard.py`, which fails on
SSN- and DoD ID-shaped numbers and on any PDF or image file.

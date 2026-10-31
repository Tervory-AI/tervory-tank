# zenas.apply

## 1.0.2
- Eval-only patch. Adds 2 `must_refuse` cases the code really refuses: for a ZA tenant, an SA ID that survives masking inside a longer reference or account number stops the prompt before any provider outside South Africa (IDENTIFIER_REFUSED, no model call). Every 1.0.1 case is kept byte-for-byte. Runtime code is copied unchanged from 1.0.1. Version 1.0.1 is untouched.

## 1.0.1
- Eval-only patch: adds refusal evidence and deterministic expectations. Runtime code is copied unchanged from 1.0.0. Existing versions are untouched.

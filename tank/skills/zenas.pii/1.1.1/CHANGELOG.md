# zenas.pii

## 1.1.1
- Eval-only patch. Adds 3 `must_refuse` cases the code really refuses: a request to return an SA ID, SSN or account number unmasked still comes back masked. Every 1.1.0 case is kept byte-for-byte. Runtime code is copied unchanged from 1.1.0. Version 1.1.0 is untouched.

## 1.1.0
- Party and company names become [Party A], [Party B], and so on.
- Email addresses, deal amounts, deal dates, case numbers, and registration numbers are masked.
- 1.0.0 identifier checks are unchanged.

## 1.0.0
- First version. Identifiers are replaced with placeholders. The raw value is not returned.

# zenas.retrieve

## 1.0.1
- Eval-only patch. Adds 3 `must_refuse` cases the code really refuses: a jurisdiction Zenas does not cover (uk), an unlabelled client memo, and a citation from another jurisdiction all return nothing. Every 1.0.0 case is kept byte-for-byte. Runtime code is copied unchanged from 1.0.0. Version 1.0.0 is untouched.

## 1.0.0
- First version. Citation, full text, then meaning, filtered by jurisdiction and as-at date. Code only.

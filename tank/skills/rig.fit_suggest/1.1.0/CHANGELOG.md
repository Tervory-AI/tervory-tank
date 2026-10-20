# rig.fit_suggest

## 1.1.0
- The fit list comes from the catalogue. Exact product fits come first, then a family the catalogue already names.
- A part is included only when that list supports it. The model cannot add one.
- The model writes one sentence of explanation, on the existing `rig.fit_suggest` route. Evals pass `model_text` so they do not call it.
- 1.0.0 is unchanged. This version is not approved.

## 1.0.0
- First version. Output is always source suggested and unapproved.

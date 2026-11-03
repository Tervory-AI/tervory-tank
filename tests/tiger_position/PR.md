# Tiger TG2: approved price-position views

Branch `codex/tiger-w4`, started from main `c4e1395ec00831561e26227c602a22dfea7ad915`.
Design register read from `codex/tiger-figma` at
`115cae58d4ac219a40989f69902c182d94ecf471`, Approved 3 Nov 15:20 PT.
No PR creation, main merge, deployment or live tenant changes by this task.

## Gate 1: Tank review API

`GET /v1/access/tiger/matches` returns only the authenticated tenant's suggested
and rejected matches with their evidence, newest first, bounded to 100. It uses
the existing Tiger entitlement check and writes a $0 Tiger receipt.

Undo uses the same durable confirmation binding as reject. Only that tenant's
rejected row can move to suggested; confirmed remains final. Reject/undo use a
conditional UPDATE so a concurrent decision cannot overwrite another state.
Both new tools are registered; only Undo enters confirmed dispatch. Explicit
commands remain code-only. Existing personal-token tool expectations are updated.

Validation: the competitors, personal-token and Command suites passed 135 tests
with 48 existing Command database cases initially skipped. All 86 Command tests
then passed against an isolated local pgserver, including those database cases.
The explicit planner regression and Ruff E9/F also pass.

## Unframed states

No additional visible copy will be invented for loading, failed reads, failed
decisions or unavailable site-check metadata. These states need approved frames.
The rest of the approved views continue independently. Read failure must not be
presented as an empty account or a successful mutation.

Workspace implementation and screenshot evidence follow in gate 2.

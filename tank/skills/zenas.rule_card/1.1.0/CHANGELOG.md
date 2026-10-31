# 1.1.0

Eval evidence: a true dated quote is approvable, and a quote with an altered
date is refused. The root fix is in the room (agents/zenas/core/engine.py):
quotes are cite-checked UNMASKED, word for word, and masked only afterwards.
A masked quote is rechecked only through the fingerprint of the exact words.


Root fix for a made-up-case miss on ZA ([2026] ZACAC 1). The model quoted a
sentence containing "08 March 2023". Rule-card cleaning masks dates and other
identifiers before cite-check ("[Date]"), so the quote no longer matched the
judgment, strict cite-check failed, and the answer became "could not verify".

Boston showed the same class on 1 F.2d 8, 10 and 11 (1924 opinions):
"March 4, 1922" is masked as [Date] and the patent number "1,237,432" as
[Amount]. Two answers became "could not verify" and one was refused as "a rule
card holds law only".

The prompt now asks for whole sentences with no dates, amounts, patent or case
numbers, ID or phone numbers, email or street addresses, and asks for them to be
kept out of every other card field (QUOTE_RULE). The room's rule-card prompt in
agents/zenas/core/service.py carries the identical line. The mask and
cite-check are unchanged: in the room a dated quote is still masked and
the answer is still "could not verify" (tests/test_zenas_rule_card_dated_quotes.py).
Minor version because run.py's prompt changed. Every 1.0.1 case is kept, plus
one positive case. 1.0.1 is untouched.

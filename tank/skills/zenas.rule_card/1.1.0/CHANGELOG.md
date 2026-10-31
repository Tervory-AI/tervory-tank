# 1.1.0

Root fix for a made-up-case miss on ZA ([2026] ZACAC 1). The model quoted a
sentence containing "08 March 2023". Rule-card cleaning masks dates and other
identifiers before cite-check ("[Date]"), so the quote no longer matched the
judgment, strict cite-check failed, and the answer became "could not verify".

The prompt now asks for whole sentences with no dates, ID or phone numbers,
email or street addresses (QUOTE_RULE). The room's rule-card prompt in
agents/zenas/core/service.py carries the identical line. The mask and
cite-check are unchanged: in the room a dated quote is still masked and
the answer is still "could not verify" (tests/test_zenas_rule_card_dated_quotes.py).
Minor version because run.py's prompt changed. Every 1.0.1 case is kept, plus
one positive case. 1.0.1 is untouched.

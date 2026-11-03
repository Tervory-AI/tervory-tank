"""Fixed writing formats. Limits are verified publisher limits, never advice."""
from dataclasses import dataclass
from typing import Literal

FormatName = Literal[
    'product description', 'Google Business Profile post', 'Facebook post',
    'Instagram caption', 'LinkedIn post', 'X post', 'email',
    'page meta description', 'article',
]


@dataclass(frozen=True)
class Format:
    limit: int | None
    source: str | None
    checked: str = '2026-11-03'
    note: str = ''


FORMATS = {
    'product description': Format(None, None, note='No platform specified; no universal limit.'),
    'Google Business Profile post': Format(None,
        'https://developers.google.com/my-business/reference/rest/v4/accounts.locations.localPosts',
        note='Official summary field has no published length limit; do not infer 1500.'),
    'Facebook post': Format(None, 'https://developers.facebook.com/docs/pages-api/posts/',
        note='No verified official organic post limit found.'),
    'Instagram caption': Format(2200,
        'https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/error-codes',
        checked='2026-11-03',
        note='HTTP 400, code 36004, subcode 2207010; character limit only.'),
    'LinkedIn post': Format(3000, 'https://www.linkedin.com/help/linkedin/answer/a527226'),
    'X post': Format(280, 'https://docs.x.com/fundamentals/counting-characters',
        note='Standard post; twitter-text weighted length, NFC, URLs and emoji.'),
    'email': Format(None, None, note='Subject and body; no provider specified, no universal draft limit.'),
    'page meta description': Format(None, 'https://developers.google.com/search/docs/appearance/snippet',
        note='Google explicitly specifies no length limit; display truncation varies.'),
    'article': Format(None, None, note='No publishing platform specified; no universal limit.'),
}


def length(text: str, name: str) -> int:
    if name == 'X post':
        from twitter_text import parse_tweet
        return parse_tweet(text).weightedLength
    return len(text)


def instruction(name: str | None) -> str:
    if name is None:
        return ''
    spec = FORMATS[name]
    return (f'Format: {name}' + (' (subject and body)' if name == 'email' else '')
            + f'. Length limit: {spec.limit if spec.limit is not None else "none verified"}.'
            + (' Count with X weighted character rules.' if name == 'X post' else ''))


def check_limit(report: dict, text: str, name: str | None) -> dict:
    if name is None:
        return report
    spec = FORMATS[name]
    count = length(text, name)
    report = {**report, 'format': name, 'length': {'count': count, 'limit': spec.limit,
              'unit': 'weighted characters' if name == 'X post' else 'Unicode code points',
              'source': spec.source, 'checked': spec.checked}}
    if spec.limit is not None and count > spec.limit:
        issue = {'source': 'format', 'rule': 'over_limit', 'count': count, 'limit': spec.limit,
                 'message': f'{count} characters; limit {spec.limit}.'}
        report['issues'] = [issue, *report['issues']][:200]
        report['issue_count'] += 1
        report['truncated'] = report['issue_count'] > 200 or report['truncated']
    return report

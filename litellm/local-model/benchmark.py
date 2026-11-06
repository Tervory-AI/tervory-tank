"""Measure real CPU inference. This is not the Tank end-to-end proof."""
import json
import statistics
import urllib.request
from urllib.parse import urlsplit

CASES = [
    ('classify', 'Reply with exactly billing or technical. Classify: I was charged twice.', 'billing'),
    ('extract', 'Extract the invoice number as JSON with key invoice: Invoice INV-204 was paid.', 'INV-204'),
    ('route', 'Classify this request as search or calculate. Output only the label. Request: Find the official Python documentation.', 'search'),
    ('draft', 'Write one short sentence thanking a customer for their patience.', None),
]


def benchmark(base='http://127.0.0.1:18089', model='local'):
    address = urlsplit(base)
    if address.scheme != 'http' or address.hostname not in {'127.0.0.1', '::1'} or address.username:
        raise ValueError('The CPU benchmark accepts only a cloud-local loopback server')
    if model not in {'local', 'local-large'}:
        raise ValueError('The CPU benchmark accepts only the two local models')
    records = []
    for kind, prompt, expected in CASES * 3:
        request = urllib.request.Request(base + '/v1/chat/completions', data=json.dumps({
            'model': model, 'messages': [{'role': 'system', 'content': 'Follow the output format exactly. Return only the requested answer, without explanation.'}, {'role': 'user', 'content': prompt}],
            'max_tokens': 64, 'temperature': 0, 'cache_prompt': False,
        }).encode(), headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=120) as response:
            data = json.load(response)
        content = data['choices'][0]['message']['content']
        assert content.strip() and (expected is None or expected.lower() in content.lower()), (kind, content)
        records.append({'task': kind, 'timings': data['timings'], 'tokens': data['usage'], 'content': content})
    print(json.dumps({'model': model, 'threads': 8,
        'median_generation_tokens_per_second': statistics.median(r['timings']['predicted_per_second'] for r in records),
        'records': records}, indent=2))


if __name__ == '__main__':
    import sys
    benchmark(sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:18089', sys.argv[2] if len(sys.argv) > 2 else 'local')

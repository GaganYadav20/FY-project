"""Test the updated routing logic."""
from app.graph.routing_logic import classify_tier

test_queries = [
    ('what is rbi policy in 2026',       'complex'),
    ('what is the rbi monetary policy',   'complex'),
    ('what is repo rate',                 'complex'),
    ('what is inflation',                 'complex'),
    ('gdp growth forecast for india',     'complex'),
    ('what is ebitda',                    'simple'),
    ('define p/e ratio',                  'simple'),
    ('nav of axis bluechip fund',         'simple'),
    ('what does sebi stand for',          'simple'),
    ('current stock price of reliance',   'simple'),
    ('compare hdfc and icici home loans', 'complex'),
    # RBI queries always go complex (full pipeline) even if phrased as verify
    ('did rbi raise rates last week',     'complex'),
]

print('Query Routing Validation:')
print('=' * 75)
all_pass = True
for query, expected in test_queries:
    actual = classify_tier(query)
    status = 'PASS' if actual == expected else f'FAIL (expected {expected})'
    print(f'{status:25} | {actual.upper():8} | {query}')
    if actual != expected:
        all_pass = False

print('=' * 75)
print('ALL TESTS PASSED' if all_pass else 'SOME TESTS FAILED')

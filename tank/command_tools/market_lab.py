"""market_lab command declarations; argument classes remain exported by command."""
TOOLS = {'market_lab': ['market_lab.research']}
FOUNDER_TOOLS = []
TENANT_ADMIN_TOOLS = []
ADMIN_ONLY_TOOLS = frozenset([])
REQUEST_BODY_TOOLS = frozenset([])
CONFIRMED = frozenset([])

def adapters(command):
    return {
        'market_lab.research': command.Adapter('POST', '/v1/research', command.QuestionArgs, 'Research a market question', True, 'paid_run', None),
    }

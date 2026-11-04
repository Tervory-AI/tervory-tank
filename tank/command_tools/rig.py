"""rig command declarations; argument classes remain exported by command."""
TOOLS = {'rig': ['rig.search', 'rig.ask', 'rig.quote.confirm_payment']}
FOUNDER_TOOLS = []
TENANT_ADMIN_TOOLS = ['rig.quote.confirm_payment']
ADMIN_ONLY_TOOLS = frozenset(['rig.quote.confirm_payment'])
REQUEST_BODY_TOOLS = frozenset([])
CONFIRMED = frozenset(['rig.quote.confirm_payment'])

def adapters(command):
    return {
        'rig.search': command.Adapter('GET', '/v1/rig/search', command.QueryArgs, 'Search the product catalogue'),
        'rig.ask': command.Adapter('POST', '/v1/rig/ask', command.RigAskArgs, 'Ask about a product', True, 'paid_run'),
        'rig.quote.confirm_payment': command.Adapter('POST', '/v1/access/rig/admin/confirm-store-payment', command.RigConfirmPaymentArgs, 'rig.quote.confirm_payment'),
    }

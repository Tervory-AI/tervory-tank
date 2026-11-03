"""zenas command declarations; argument classes remain exported by command."""
TOOLS = {'zenas': ['zenas.ask', 'zenas.matters', 'zenas.review', 'zenas.watch.add', 'zenas.watch.list', 'zenas.watch.enable', 'zenas.watch.disable']}
FOUNDER_TOOLS = []
TENANT_ADMIN_TOOLS = []
ADMIN_ONLY_TOOLS = frozenset([])
REQUEST_BODY_TOOLS = frozenset([])
CONFIRMED = frozenset([])

def adapters(command):
    return {
        'zenas.ask': command.Adapter('POST', '/v1/zenas/answers', command.ZenasAskArgs, 'Ask a civil law question', True, 'paid_run', None),
        'zenas.matters': command.Adapter('POST', '/v1/zenas/matters', command.MatterArgs, 'Create a matter', False, 'other', None),
        'zenas.watch.add': command.Adapter('POST', '/v1/zenas/regulations/watches', command.ZenasWatchAddArgs, 'zenas.watch.add', False, 'other', None),
        'zenas.watch.list': command.Adapter('GET', '/v1/zenas/regulations/watches', command.EmptyArgs, 'zenas.watch.list', False, 'other', None),
        'zenas.watch.enable': command.Adapter('POST', '/v1/zenas/regulations/watches/{watch_id}', command.ZenasWatchIdArgs, 'zenas.watch.enable', False, 'other', None),
        'zenas.watch.disable': command.Adapter('POST', '/v1/zenas/regulations/watches/{watch_id}', command.ZenasWatchIdArgs, 'zenas.watch.disable', False, 'other', None),
        'zenas.review': command.Adapter('POST', '/v1/zenas/contract-reviews', command.ReviewArgs, 'Review a contract', True, 'paid_run', None),
    }

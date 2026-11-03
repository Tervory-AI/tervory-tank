"""tiger command declarations; argument classes remain exported by command."""
TOOLS = {'tiger': ['tiger.watch', 'tiger.read', 'tiger.match', 'tiger.match.confirm', 'tiger.match.reject', 'tiger.position', 'tiger.alerts']}
FOUNDER_TOOLS = []
TENANT_ADMIN_TOOLS = []
ADMIN_ONLY_TOOLS = frozenset([])
REQUEST_BODY_TOOLS = frozenset([])
CONFIRMED = frozenset(['tiger.match', 'tiger.match.confirm', 'tiger.match.reject'])

def adapters(command):
    return {
        'tiger.match': command.Adapter('POST', '/v1/access/tiger/match', command.EmptyArgs, 'tiger.match', False, 'other', None),
        'tiger.match.confirm': command.Adapter('POST', '/v1/access/tiger/match/confirm', command.TigerMatchArgs, 'tiger.match.confirm', False, 'other', None),
        'tiger.match.reject': command.Adapter('POST', '/v1/access/tiger/match/reject', command.TigerMatchArgs, 'tiger.match.reject', False, 'other', None),
        'tiger.position': command.Adapter('GET', '/v1/access/tiger/position', command.EmptyArgs, 'tiger.position', False, 'other', None),
        'tiger.watch': command.Adapter('POST', '/v1/tiger/watchlist', command.WatchArgs, 'Start a price watch', True, 'paid_run', None),
        'tiger.read': command.Adapter('GET', '/v1/tiger/observations', command.UrlArgs, 'Read price observations', False, 'other', None),
        'tiger.alerts': command.Adapter('GET', '/v1/command/tiger/alerts', __import__('tiger_alerts').AlertsArgs, 'tiger.alerts', False, 'other', None),
    }

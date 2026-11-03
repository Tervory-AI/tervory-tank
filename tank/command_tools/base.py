"""base command declarations; argument classes remain exported by command."""
TOOLS = {'base': ['base.batch', 'base.search', 'base.find', 'base.list.save', 'base.lists', 'base.list.show', 'base.list.export', 'base.list.to_crm']}
FOUNDER_TOOLS = ['base.audit.start', 'base.audit.csv', 'base.audit.review']
TENANT_ADMIN_TOOLS = []
ADMIN_ONLY_TOOLS = frozenset([])
REQUEST_BODY_TOOLS = frozenset(['base.audit.review', 'base.audit.start', 'base.list.save', 'base.list.to_crm'])
CONFIRMED = frozenset(['base.audit.review', 'base.audit.start', 'base.list.save', 'base.list.to_crm'])

def adapters(command):
    return {
        'base.audit.start': command.Adapter('POST', '/v1/command/base/audits/start', command.AuditStartArgs, 'base.audit.start', False, 'other', None),
        'base.audit.csv': command.Adapter('GET', '/v1/command/base/audits/export', command.AuditCsvArgs, 'base.audit.csv', False, 'other', None),
        'base.audit.review': command.Adapter('POST', '/v1/command/base/audits/review', command.AuditReviewArgs, 'base.audit.review', False, 'other', None),
        'base.batch': command.Adapter('POST', '/v1/base/run', command.BaseBatchArgs, 'Start a Base batch', True, 'paid_run', None),
        'base.search': command.Adapter('GET', '/v1/base/records', command.BaseSearchArgs, 'Read Base records', False, 'other', None),
        'base.find': command.Adapter('GET', '/v1/command/base/lists/find', command.FindArgs, 'base.find', False, 'other', None),
        'base.list.save': command.Adapter('POST', '/v1/command/base/lists/save', command.SaveArgs, 'base.list.save', False, 'other', None),
        'base.lists': command.Adapter('GET', '/v1/command/base/lists', command.Body, 'base.lists', False, 'other', None),
        'base.list.show': command.Adapter('GET', '/v1/command/base/lists/show', command.ListArgs, 'base.list.show', False, 'other', None),
        'base.list.export': command.Adapter('GET', '/v1/command/base/lists/export', command.ListArgs, 'base.list.export', False, 'other', None),
        'base.list.to_crm': command.Adapter('POST', '/v1/command/base/lists/to-crm', command.SendArgs, 'base.list.to_crm', False, 'other', None),
    }

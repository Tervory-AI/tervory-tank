"""skala command declarations; argument classes remain exported by command."""
TOOLS = {}
FOUNDER_TOOLS = ['skala.list', 'skala.evals', 'skala.approve', 'skala.retire', 'ledger.receipts', 'ledger.savings']
TENANT_ADMIN_TOOLS = []
ADMIN_ONLY_TOOLS = frozenset([])
REQUEST_BODY_TOOLS = frozenset([])
CONFIRMED = frozenset([])

def adapters(command):
    return {
        'skala.list': command.Adapter('GET', '/v1/skala', command.EmptyArgs, 'List skills', False, 'other', None),
        'skala.evals': command.Adapter('POST', '/v1/skala/{skill_id}/{version}/evals', command.SkillVersionArgs, 'Run skill evaluations', True, 'paid_run', None),
        'skala.approve': command.Adapter('POST', '/v1/skala/{skill_id}/{version}/approve', command.SkillVersionArgs, 'Approve a skill version', False, 'approve_skill', None),
        'skala.retire': command.Adapter('POST', '/v1/skala/{skill_id}/{version}/retire', command.SkillVersionArgs, 'Retire a skill version', False, 'retire', None),
        'ledger.receipts': command.Adapter('GET', '/v1/proof', command.ProofArgs, 'Read ledger receipts', False, 'other', None),
        'ledger.savings': command.Adapter('GET', '/v1/proof', command.SavingsArgs, 'Read recorded costs and savings', False, 'other', None),
    }

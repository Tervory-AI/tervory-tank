"""radix command declarations; argument classes remain exported by command."""
TOOLS = {'radix': ['radix.scan', 'radix.repo.scan', 'radix.repo.findings']}
FOUNDER_TOOLS = ['radix.domain.prove', 'radix.passive.scan', 'radix.findings']
TENANT_ADMIN_TOOLS = []
ADMIN_ONLY_TOOLS = frozenset([])
REQUEST_BODY_TOOLS = frozenset([])
CONFIRMED = frozenset(['radix.repo.scan'])

def adapters(command):
    return {
        'radix.domain.prove': command.Adapter('POST', '/v1/radix/passive/domains', command.RadixDomainArgs, 'radix.domain.prove', False, 'other', None),
        'radix.passive.scan': command.Adapter('POST', '/v1/radix/passive/scans', command.RadixPassiveArgs, 'radix.passive.scan', False, 'other', None),
        'radix.findings': command.Adapter('GET', '/v1/radix/passive/scans/{scan_id}/findings', command.RadixFindingsArgs, 'radix.findings', False, 'other', None),
        'radix.repo.scan': command.Adapter('POST', '/v1/command/radix/repo/scan', command.UploadRef, 'radix.repo.scan', False, 'other', None),
        'radix.repo.findings': command.Adapter('GET', '/v1/command/radix/repo/findings', command.RadixFindingsArgs, 'radix.repo.findings', False, 'other', None),
        'radix.scan': command.Adapter('POST', '/v1/skala/scan.static/run', command.ScanArgs, 'Scan supplied source text', False, 'other', 'scan.static'),
    }

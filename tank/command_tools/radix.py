"""radix command declarations; argument classes remain exported by command."""
TOOLS = {'radix': ['radix.scan', 'radix.repo.scan', 'radix.repo.findings', 'radix.watch', 'radix.unwatch', 'radix.watches', 'radix.changes']}
FOUNDER_TOOLS = ['radix.domain.prove', 'radix.passive.scan', 'radix.findings']
TENANT_ADMIN_TOOLS = []
ADMIN_ONLY_TOOLS = frozenset([])
REQUEST_BODY_TOOLS = frozenset([])
CONFIRMED = frozenset(['radix.repo.scan'])

def adapters(command):
    return {
        'radix.watch': command.Adapter('POST', '/v1/radix/passive/watch', command.RadixWatchArgs, 'radix.watch'),
        'radix.unwatch': command.Adapter('POST', '/v1/radix/passive/unwatch', command.RadixDomainArgs, 'radix.unwatch'),
        'radix.watches': command.Adapter('GET', '/v1/radix/passive/watches', command.EmptyArgs, 'radix.watches'),
        'radix.changes': command.Adapter('GET', '/v1/radix/passive/changes', command.RadixDomainArgs, 'radix.changes'),
        'radix.domain.prove': command.Adapter('POST', '/v1/radix/passive/domains', command.RadixDomainArgs, 'radix.domain.prove'),
        'radix.passive.scan': command.Adapter('POST', '/v1/radix/passive/scans', command.RadixPassiveArgs, 'radix.passive.scan'),
        'radix.findings': command.Adapter('GET', '/v1/radix/passive/scans/{scan_id}/findings', command.RadixFindingsArgs, 'radix.findings'),
        'radix.repo.scan': command.Adapter('POST', '/v1/command/radix/repo/scan', command.UploadRef, 'radix.repo.scan'),
        'radix.repo.findings': command.Adapter('GET', '/v1/command/radix/repo/findings', command.RadixFindingsArgs, 'radix.repo.findings'),
        'radix.scan': command.Adapter('POST', '/v1/skala/scan.static/run', command.ScanArgs, 'Scan supplied source text', False, 'other', 'scan.static'),
    }

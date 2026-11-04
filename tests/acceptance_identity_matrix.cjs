// Actual tenant resolver with disposable Clerk/report fixtures. No live tokens or writes.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');
const ts = require(path.join(root, 'workspace/node_modules/typescript'));
let session, reads, reports;
const exportsFixture = {};
vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(root, 'workspace/lib/tenant.ts'), 'utf8'), {
  compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022},
}).outputText, {
  exports: exportsFixture, Buffer, process: {env: {}},
  require(name) {
    if (name === 'node:crypto') return require(name);
    if (name === './tank') return {ensureCaseStudyReports: async tenant => {reports.push(tenant);}};
    if (name === '@clerk/nextjs/server') return {
      auth: async () => session,
      currentUser: async () => {throw Error('Unexpected personal organization creation');},
      clerkClient: async () => ({
        organizations: {
          getOrganization: async ({organizationId}) => {reads.push(organizationId); return {id: organizationId, name: 'Disposable fixture'};},
          createOrganization: async () => {throw Error('Unexpected organization mutation');},
        },
        users: {getOrganizationMembershipList: async () => {throw Error('Unexpected fallback membership lookup');}},
      }),
    };
    throw Error(`Unmocked dependency ${name}`);
  },
});
const {activeTenant, currentTenant, tenantIdFor} = exportsFixture;
function reset(userId, orgId, orgRole) {session = {userId, orgId, orgRole}; reads = []; reports = [];}
(async () => {
  reset(null, null, null);
  assert.equal(await activeTenant(), null);
  await assert.rejects(currentTenant(), /not signed in/);
  assert.deepEqual(reads, []); assert.deepEqual(reports, []);
  reset('fixture-user', null, 'org:member');
  assert.equal(await activeTenant(), null);
  assert.deepEqual(reads, []); assert.deepEqual(reports, []);
  for (const role of ['org:member', 'org:admin', 'org:reviewer']) {
    for (const orgId of ['org_acceptance_a', 'org_acceptance_b', 'org_acceptance_a']) {
      reset('fixture-user', orgId, role);
      for (const resolver of [activeTenant, currentTenant]) {
        const tenant = await resolver();
        assert.equal(tenant.orgId, orgId);
        assert.equal(tenant.tenantId, tenantIdFor(orgId));
        assert.equal(tenant.userId, 'fixture-user');
        assert.notEqual(tenant.tenantId, tenantIdFor(orgId === 'org_acceptance_a' ? 'org_acceptance_b' : 'org_acceptance_a'));
      }
      assert.deepEqual(reads, [orgId, orgId]);
      assert.equal(reports.length, 2);
      assert(reports.every(row => row.orgId === orgId));
    }
  }
  console.log('PASS: actual tenant resolver: signed out, no active org without mutation, member/admin/reviewer, A/B/A organization switching and report scoping. Identity resolution alone does not prove entitlements.');
})().catch(error => {console.error(error); process.exitCode = 1;});

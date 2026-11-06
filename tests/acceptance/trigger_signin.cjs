const assert = require('node:assert/strict');
const path = require('node:path');
const root = path.resolve(__dirname, '../..');
process.env.COMMAND_TEST_TOOLS = path.join(root, 'workspace/node_modules');
const { workspace } = require('../command_acceptance_20261031/workspace_loader.cjs');
const jwt = require(path.join(process.env.COMMAND_TEST_TOOLS, 'next-auth/jwt'));
const provider = require(path.join(process.env.COMMAND_TEST_TOOLS, 'next-auth/providers/zitadel'));
const next = require(path.join(process.env.COMMAND_TEST_TOOLS, 'next/server'));
const env = {
  TANK_URL: 'https://tank.example.invalid',
  TANK_API_KEY: 'offline-acceptance-placeholder',
  TRIGGER_SIGNIN_WORKSPACE_SECRET: require('node:crypto').randomBytes(32).toString('hex'),
  TRIGGER_SIGNIN_WORKSPACE_CLIENT_ID: '30002@tervory',
  TRIGGER_SIGNIN_ORG_TENANTS: JSON.stringify({'60001': '00000000-0000-4000-8000-000000000011', '60002': '00000000-0000-4000-8000-000000000012'}),
};
const runtime = { issuer: 'https://auth.tervory.com', workspace_client_id: env.TRIGGER_SIGNIN_WORKSPACE_CLIENT_ID };
const controls = [];
const load = workspace({env, browser: {location: {search: '?callbackUrl=%2Frig', href: 'https://app.tervory.com/rig'}}, fetch: () => {throw Error('Acceptance must remain offline');}, mocks: {
  'react/jsx-runtime': {jsx: (type, props) => ({type, props}), jsxs: (type, props) => ({type, props})},
  'next-auth/react': {signIn: (...args) => {controls.push({name: 'signIn', args});},
                     signOut: (...args) => {controls.push({name: 'signOut', args});}},
  'next-auth/providers/zitadel': provider,
  './trigger-signin-runtime': {signinRuntime: async () => runtime},
  '@/lib/trigger-signin-runtime': {signinRuntime: async () => runtime},
  'next/server': next,
}});
const principal = load('lib/trigger-signin-principal.ts');
const claims = {sub: '50001', exp: Math.floor(Date.now() / 1000) + 3600,
  [principal.ORG_CLAIM]: '60001',
  [principal.ROLES_CLAIM]: {org_admin: {'60001': 'tenant-a'}, member: {'60002': 'tenant-b'}},
  email: 'founder@example.invalid', publicMetadata: {role: 'org_admin'},
};
async function acceptance(row) {
  const options = await load('lib/trigger-signin-options.ts').signinOptions();
  const callbacks = options.callbacks;
  const token = await callbacks.jwt({token: {}, account: {id_token: 'synthetic-native-token'}, profile: claims});
  if (row === 'S01') {
    const buttons = load('app/trigger-signin-provider.tsx');
    buttons.TriggerSigninButton({register: true}).props.onClick();
    assert.equal(controls[0].args[0], 'trigger-signin');
    assert.equal(controls[0].args[2].prompt, 'create');
    buttons.TriggerSigninButton({register: false}).props.onClick();
    assert.equal(controls[1].args[2].prompt, 'select_account');
    assert.equal(options.providers[0].options.id, 'trigger-signin');
    assert.deepEqual(Array.from(options.providers[0].options.checks), ['pkce', 'state', 'nonce']);
    assert.equal(options.providers[0].options.client.token_endpoint_auth_method, 'none');
    const encrypted = await jwt.encode({token, secret: env.TRIGGER_SIGNIN_WORKSPACE_SECRET});
    const decoded = await jwt.decode({token: encrypted, secret: env.TRIGGER_SIGNIN_WORKSPACE_SECRET});
    const session = await callbacks.session({session: {}, token: decoded});
    assert.equal(session.principal.userId, '50001');
    assert.equal(session.principal.orgRole, 'org:admin');
    assert.equal(session.idToken, undefined);
    assert(!JSON.stringify(session).includes('synthetic-native-token'));
    const forged = {...claims, [principal.ROLES_CLAIM]: {member: {'60001': 'tenant-a'}}};
    assert.equal(principal.signinPrincipal(forged).orgRole, null);
    for (const host of ['app', 'base', 'tiger', 'market-lab', 'tisan', 'radix', 'skala', 'tank', 'rig', 'zenas', 'trigger']) {
      const target = `https://${host}.tervory.com/`;
      assert.equal(await callbacks.redirect({url: target, baseUrl: 'https://app.tervory.com'}), target);
    }
    assert.equal(await callbacks.redirect({url: 'https://attacker.invalid/', baseUrl: 'https://app.tervory.com'}), 'https://app.tervory.com');
  } else if (row === 'S02') {
    load('app/trigger-signin-provider.tsx').SignoutButton().props.onClick();
    assert.equal(controls[0].name, 'signOut');
    assert.equal(controls[0].args[0].callbackUrl, '/api/trigger-signin/signed-out');
    const response = await load('app/api/trigger-signin/signed-out/route.ts').GET();
    const target = new URL(response.headers.get('location'));
    assert.equal(target.origin, runtime.issuer);
    assert.equal(target.pathname, '/oidc/v1/end_session');
    assert.equal(target.searchParams.get('client_id'), runtime.workspace_client_id);
    assert.equal(target.searchParams.get('post_logout_redirect_uri'), 'https://app.tervory.com/sign-in');
    assert.equal(target.searchParams.get('id_token_hint'), null);
    const expired = {...token, principal: {...token.principal, expiresAt: Date.now() - 1}};
    assert.equal((await callbacks.session({session: {}, token: expired})).principal, undefined);
  } else if (row === 'S03') {
    const switched = await callbacks.jwt({token, trigger: 'update', session: {orgId: '60002', userId: 'forged', orgRole: 'org:admin'}});
    assert.equal(switched.principal.tenantId, '00000000-0000-4000-8000-000000000012');
    assert.equal(switched.principal.userId, '50001');
    assert.equal(switched.principal.orgRole, null);
    await assert.rejects(callbacks.jwt({token, trigger: 'update', session: {orgId: '60003'}}));
    const returned = await callbacks.jwt({token, trigger: 'update', session: {orgId: '60001'}});
    assert.equal(returned.principal.tenantId, '00000000-0000-4000-8000-000000000011');
  } else if (row === 'S06') {
    const gate = load('app/review/founder.ts');
    assert.equal(gate.isListedFounder('client-subject', 'founder-subject'), false);
    assert.equal(gate.founderDenial('client-subject', 'founder-subject').status, 404);
    assert.equal(gate.isListedFounder('founder-subject', 'founder-subject'), true);
    assert.equal(gate.isListedFounder('founder@example.invalid', 'founder-subject'), false);
  } else throw Error('Unknown acceptance row');
  console.log(`${row} passed`);
}
acceptance(process.argv[2]).catch(error => {console.error(error); process.exitCode = 1;});

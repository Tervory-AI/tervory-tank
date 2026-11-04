// Existing Workspace contract fixtures represent tenants already onboarded in US.
// Denials and cross-region routing use the real helper in platform/regions.cjs.
module.exports = target => new URL(target, 'http://fixture.invalid').pathname.startsWith('/v1/tenants/')
  ? Response.json({home_region:'us-east'}) : null;

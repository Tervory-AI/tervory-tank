# Tank RLS runtime connection

Both Compose stacks now accept `TANK_DATABASE_URL` for **Tank only**. The
existing Postgres, backup and Hermes connection settings stay independent.
This configuration-only change redeploys the Boston main stack and ZA stack.

Once any table in `tank`, `base` or `agent_*` has RLS enabled, Tank's existing
startup check rejects a superuser or BYPASSRLS runtime login and requires a
separate admin pool. Do not disable RLS or relax that startup check to recover.

In each region, an operator must provision and verify two distinct logins before
restarting Tank:

- Runtime: LOGIN, NOSUPERUSER, NOBYPASSRLS, NOCREATEDB, NOCREATEROLE; no membership
  in the administrator role. Set its connection URI as `TANK_DATABASE_URL`.
- Schema/admin: the existing schema owner with BYPASSRLS, supplied through
  `TANK_ADMIN_DATABASE_URL`; set its exact role name as `TANK_RLS_ADMIN_ROLE`.
  Tank applies idempotent schema changes using this connection.

Keep connection values in Coolify. URL-encode password characters in connection
URIs; never write actual credentials to a terminal command, report or chat.
The Compose fallback preserves previous deployments but does not make a privileged
connection safe after RLS activation. Setting only the admin connection is
insufficient: the runtime login must also be restricted.

Reuse the existing grants pattern in `tests/test_tenant_rls.py`: runtime needs
USAGE on the relevant schemas, SELECT/INSERT/UPDATE/DELETE on their tables and
USAGE/SELECT on sequences. Review all schemas Tank actually accesses and grant
only the necessary objects. Configure owner-specific default privileges for
future tables/sequences created by the schema administrator, so later startup
DDL does not silently leave inaccessible objects. Do not grant schema ownership,
CREATE, role membership, or BYPASSRLS to the runtime login. The test fixture is a
disposable example, not a production provisioning script.

Validate without printing passwords: current_user and rolsuper/rolbypassrls on
both pools, role membership, schema/table/sequence privileges, and successful
schema application through the owner. Then verify tenant A cannot read or update
tenant B through the runtime pool, including the newly protected Tisan quote
relations; verify the admin path works only in its intended administrative scope.
Existing real-Postgres isolation tests are in `tests/test_tenant_rls.py` and require
an explicitly disposable `RLS_TEST_DATABASE_URL`. Never point them at production.

After saving all three settings in both regional apps, deploy and verify Tank
startup and health in both regions. A previous healthy container or a finished
build alone does not prove the new pools are correctly configured. Preserve
backups and existing database owners; no production role/grant changes are
performed by this patch.

"""Watch-volume replay protection and paid-run checkpoints; no production DB login."""
import hashlib
import json
import time


class BrainState:
    def __init__(self, store):
        self.db = store.db
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS ghost_assertion_nonces (
                nonce_hash TEXT PRIMARY KEY, tenant TEXT NOT NULL, expires INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS ghost_brain_runs (
                tenant TEXT NOT NULL, owner TEXT NOT NULL, id TEXT NOT NULL,
                input_hash TEXT NOT NULL, receipt TEXT,
                PRIMARY KEY(tenant,owner,id));
        """)

    async def claim(self, tenant, nonce, expires):
        with self.db:
            self.db.execute("DELETE FROM ghost_assertion_nonces WHERE expires<=?", (time.time(),))
            result = self.db.execute("INSERT OR IGNORE INTO ghost_assertion_nonces VALUES (?,?,?)",
                                     (hashlib.sha256(nonce.encode()).hexdigest(), tenant, expires))
        return result.rowcount == 1

    def start(self, tenant, owner, run_id, input_hash):
        with self.db:
            claimed = self.db.execute("INSERT OR IGNORE INTO ghost_brain_runs VALUES (?,?,?,?,NULL)",
                                      (tenant, owner, run_id, input_hash)).rowcount == 1
            row = self.db.execute("SELECT input_hash,receipt FROM ghost_brain_runs WHERE tenant=? AND owner=? AND id=?",
                                  (tenant, owner, run_id)).fetchone()
        if row[0] != input_hash:
            raise ValueError("Run ID already used for another task.")
        return claimed, json.loads(row[1]) if row[1] else None

    def save(self, receipt):
        with self.db:
            self.db.execute("UPDATE ghost_brain_runs SET receipt=? WHERE tenant=? AND owner=? AND id=?",
                            (json.dumps(receipt), receipt['tenant_id'], receipt['user_id'] or '', receipt['task_id']))

    def invalidate(self, tenant, owner):
        # Preserve accounting/deduplication, but never return forgotten private answers.
        with self.db:
            rows = self.db.execute("SELECT id,receipt FROM ghost_brain_runs WHERE tenant=? AND owner=? AND receipt IS NOT NULL",
                                   (tenant, owner)).fetchall()
            for run_id, raw in rows:
                receipt = json.loads(raw)
                receipt.update(answer=None, status='invalidated', memory_status='invalidated')
                self.db.execute("UPDATE ghost_brain_runs SET receipt=? WHERE tenant=? AND owner=? AND id=?",
                                (json.dumps(receipt), tenant, owner, run_id))


async def verified_actor(request, tenant, claimed_user=None, *, required=True):
    """Use Tank's shared verifier; old snapshots fail closed, never trust body IDs."""
    from fastapi import HTTPException
    try:
        from chassis.user_assertion import signed_user
    except ImportError:
        if required or request.headers.get('X-Tervory-User-Assertion'):
            raise HTTPException(503, 'Signed memory runtime unavailable.') from None
        return None
    actor = await signed_user(request, tenant_id=str(tenant), product='ghost',
                              nonces=BrainState(request.app.state.store),
                              required=required or bool(request.headers.get('X-Tervory-User-Assertion')))
    if actor and claimed_user is not None and claimed_user != actor.user_id:
        raise HTTPException(403, 'Memory owner does not match signed user.')
    return actor

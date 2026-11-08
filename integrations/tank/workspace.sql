-- Workspace code-only comparisons keep hypothetical tokens separate from usage.
ALTER TABLE tank.ledger ADD COLUMN IF NOT EXISTS comparison_tokens_in integer CHECK (comparison_tokens_in >= 0);
ALTER TABLE tank.ledger ADD COLUMN IF NOT EXISTS comparison_tokens_out integer CHECK (comparison_tokens_out >= 0);
CREATE OR REPLACE FUNCTION tank.price_receipt() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE chosen_family text; standard_name text; selected_name text; top_name text;
        setting tank.baseline_settings%ROWTYPE; priced numeric; selected_cost numeric; top_cost numeric;
BEGIN
    IF TG_OP='UPDATE' THEN
      INSERT INTO tank.comparison_history(ledger_id,tenant_id,region,valid_from,valid_until,comparison,reason)
      VALUES(OLD.id,OLD.tenant_id,OLD.region,coalesce(OLD.baseline_priced_at,OLD.ts),now(),
        jsonb_build_object('standard_model',OLD.standard_model,'standard_cost_usd',OLD.standard_cost_usd,
          'top_model',OLD.top_model,'top_cost_usd',OLD.top_cost_usd,'baseline_model',OLD.baseline_model,
          'baseline_cost_usd',OLD.baseline_cost_usd,'baseline_status',OLD.baseline_status,
          'baseline_priced_at',OLD.baseline_priced_at,'comparison_revision',OLD.comparison_revision),
        CASE WHEN OLD.comparison_revision=0 THEN 'default migration'
          WHEN OLD.comparison_revision=NEW.comparison_revision THEN 'price refresh' ELSE 'task override' END)
      ON CONFLICT DO NOTHING;
    END IF;
    -- A plain MVCC read: receipts never lock a shared task setting. The durable
    -- receipt-check queue catches rows committed after a repricing batch finishes.
    SELECT * INTO setting FROM tank.baseline_settings WHERE task_type=NEW.task_type;
    NEW.comparison_revision := coalesce(setting.revision,1);
    -- Invalidate all comparisons when actual costs are unknown or are vendor fees.
    IF to_jsonb(NEW)->>'research_cost_status'='unknown' OR NEW.model LIKE 'vendor:%' OR to_jsonb(NEW)->>'vendor' IS NOT NULL THEN
      NEW.baseline_model:=NULL; NEW.baseline_cost_usd:=NULL;
      NEW.standard_model:=NULL; NEW.standard_cost_usd:=NULL;
      NEW.top_model:=NULL; NEW.top_cost_usd:=NULL; NEW.baseline_status:='unpriced';
      NEW.baseline_priced_at:=now(); RETURN NEW;
    END IF;
    SELECT family INTO chosen_family FROM tank.proof_prices WHERE model=NEW.model;
    IF chosen_family IS NULL AND (NEW.rung=3 OR NEW.cache_hit) THEN
      SELECT a.family INTO chosen_family FROM tank.policy p JOIN tank.proof_prices a ON a.model=p.model
        WHERE p.task_type=NEW.task_type AND (p.tenant_id=NEW.tenant_id OR p.tenant_id IS NULL)
        ORDER BY p.tenant_id NULLS LAST LIMIT 1;
    END IF;
    standard_name:=tank.standard_model_for(chosen_family);
    selected_name:=coalesce(setting.override_model,standard_name);
    standard_name:=selected_name; -- A founder override replaces this task's comparison.
    SELECT model INTO top_name FROM tank.proof_prices WHERE family=chosen_family AND active
      ORDER BY input_usd+output_usd DESC,model LIMIT 1;
    SELECT coalesce(NEW.comparison_tokens_in,NEW.tokens_in)*input_usd+coalesce(NEW.comparison_tokens_out,NEW.tokens_out)*output_usd INTO priced
      FROM tank.proof_prices WHERE model=standard_name AND family=chosen_family AND active;
    SELECT coalesce(NEW.comparison_tokens_in,NEW.tokens_in)*input_usd+coalesce(NEW.comparison_tokens_out,NEW.tokens_out)*output_usd INTO selected_cost
      FROM tank.proof_prices WHERE model=selected_name AND family=chosen_family AND active;
    SELECT coalesce(NEW.comparison_tokens_in,NEW.tokens_in)*input_usd+coalesce(NEW.comparison_tokens_out,NEW.tokens_out)*output_usd INTO top_cost
      FROM tank.proof_prices WHERE model=top_name AND family=chosen_family AND active;
    IF coalesce(NEW.comparison_tokens_in,NEW.tokens_in)=0 AND coalesce(NEW.comparison_tokens_out,NEW.tokens_out)=0 AND NEW.cost_usd=0 AND (NEW.rung=3 OR NEW.cache_hit) THEN
      priced:=0; selected_cost:=0; top_cost:=0;
      standard_name:=coalesce(standard_name,'No AI call');
      selected_name:=coalesce(selected_name,'No AI call'); top_name:=coalesce(top_name,'No AI call');
    END IF;
    NEW.standard_model:=standard_name; NEW.standard_cost_usd:=priced;
    NEW.top_model:=top_name; NEW.top_cost_usd:=top_cost;
    NEW.baseline_model:=selected_name; NEW.baseline_cost_usd:=selected_cost;
    NEW.baseline_priced_at:=now();
    IF priced IS NULL THEN
      NEW.baseline_status := 'unpriced';
    ELSIF NEW.comparison_tokens_in IS NOT NULL OR NEW.comparison_tokens_out IS NOT NULL THEN
      NEW.baseline_status := 'estimated';
    ELSIF TG_OP='INSERT' THEN
      NEW.baseline_status := 'measured';
    ELSIF OLD.standard_cost_usd IS NOT NULL OR OLD.baseline_cost_usd IS NOT NULL THEN
      NEW.baseline_status := 're-priced';
    ELSE
      NEW.baseline_status := 'backfilled';
    END IF;
    RETURN NEW;
END $$;
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='workspace_price_comparison' AND tgrelid='tank.ledger'::regclass) THEN
      CREATE TRIGGER workspace_price_comparison BEFORE UPDATE OF comparison_tokens_in,comparison_tokens_out ON tank.ledger
        FOR EACH ROW EXECUTE FUNCTION tank.price_receipt();
    END IF;
END $$;

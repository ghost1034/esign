"""Initial standalone esign schema with signing-evidence protections."""
import importlib.util
from pathlib import Path
from alembic import op
revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None

def snapshot():
    spec = importlib.util.spec_from_file_location("baseline", Path(__file__).parents[1] / "baseline_models.py")
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module.Base.metadata

def upgrade():
    metadata = snapshot()
    bind = op.get_bind()
    enums = {}
    for table in metadata.tables.values():
        for column in table.columns:
            if getattr(column.type, "enums", None): enums[column.type.name] = column.type
    for typ in enums.values(): typ.create(bind, checkfirst=True)
    metadata.create_all(bind)
    for sql in TRIGGERS: op.execute(sql)

def downgrade():
    raise RuntimeError("Initial schema contains immutable evidence; restore a backup instead of dropping it")

TRIGGERS = ["\n        CREATE OR REPLACE FUNCTION esign_events_block_mutation()\n        RETURNS trigger AS $$\n        BEGIN\n            RAISE EXCEPTION 'esign_events is append-only: % not allowed', TG_OP;\n        END;\n        $$ LANGUAGE plpgsql;\n        ", '\n        CREATE TRIGGER trg_esign_events_append_only\n        BEFORE UPDATE OR DELETE ON esign_events\n        FOR EACH ROW EXECUTE FUNCTION esign_events_block_mutation();\n        ', "\nCREATE OR REPLACE FUNCTION esign_events_block_mutation()\nRETURNS trigger AS $$\nBEGIN\n    IF TG_OP = 'DELETE' AND EXISTS (\n        SELECT 1 FROM esign_envelopes e\n        WHERE e.id = OLD.envelope_id AND e.status = 'draft'\n    ) THEN\n        RETURN OLD;\n    END IF;\n    RAISE EXCEPTION 'esign_events is append-only: % not allowed', TG_OP;\nEND;\n$$ LANGUAGE plpgsql;\n", "\n        CREATE OR REPLACE FUNCTION esign_recipient_changes_block_mutation()\n        RETURNS trigger AS $$ BEGIN\n            RAISE EXCEPTION 'esign_recipient_changes is append-only: % not allowed', TG_OP;\n        END; $$ LANGUAGE plpgsql;\n        CREATE TRIGGER trg_esign_recipient_changes_append_only\n        BEFORE UPDATE OR DELETE ON esign_recipient_changes\n        FOR EACH ROW EXECUTE FUNCTION esign_recipient_changes_block_mutation();\n    ", "\n        CREATE FUNCTION esign_template_versions_block_update()\n        RETURNS trigger AS $$ BEGIN\n          RAISE EXCEPTION 'published e-sign template versions are immutable';\n        END; $$ LANGUAGE plpgsql;\n        CREATE TRIGGER trg_esign_template_versions_immutable\n        BEFORE UPDATE ON esign_template_versions\n        FOR EACH ROW EXECUTE FUNCTION esign_template_versions_block_update();\n    ", "\n        CREATE FUNCTION esign_webhook_attempts_block_mutation() RETURNS trigger AS $$ BEGIN\n          IF TG_OP = 'DELETE' AND current_setting('esign.retention_cleanup', true) = 'on' THEN RETURN OLD; END IF;\n          RAISE EXCEPTION 'esign_webhook_attempts is append-only';\n        END; $$ LANGUAGE plpgsql;\n        CREATE TRIGGER trg_esign_webhook_attempts_append_only BEFORE UPDATE OR DELETE ON esign_webhook_attempts\n        FOR EACH ROW EXECUTE FUNCTION esign_webhook_attempts_block_mutation();\n        CREATE FUNCTION esign_admin_events_block_mutation() RETURNS trigger AS $$ BEGIN\n          RAISE EXCEPTION 'esign_admin_events is append-only';\n        END; $$ LANGUAGE plpgsql;\n        CREATE TRIGGER trg_esign_admin_events_append_only BEFORE UPDATE OR DELETE ON esign_admin_events\n        FOR EACH ROW EXECUTE FUNCTION esign_admin_events_block_mutation();\n    "]

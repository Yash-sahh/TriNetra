"""Initial schema marker for the SQLite demo and PostgreSQL-compatible ORM."""
revision = "20260903_initial"
down_revision = None
branch_labels = None
depends_on = None
def upgrade():
    # The demo bootstraps metadata directly; production revisions are generated
    # from app.main.Base metadata before deployment.
    pass
def downgrade(): pass

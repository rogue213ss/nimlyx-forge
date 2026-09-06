"""Add V10 LLM ScriptRun fields

Revision ID: fa669dd7f54a
Revises: 5dade5238f53
Create Date: 2026-09-05 01:00:43.199433

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fa669dd7f54a'
down_revision: Union[str, Sequence[str], None] = '5dade5238f53'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('script_runs', sa.Column('provider_name', sa.String(length=50), nullable=True))
    op.add_column('script_runs', sa.Column('model_name', sa.String(length=50), nullable=True))
    op.add_column('script_runs', sa.Column('configuration', sa.Text(), nullable=True))
    op.add_column('script_runs', sa.Column('prompt_version', sa.String(length=50), nullable=True))
    op.add_column('script_runs', sa.Column('token_usage', sa.Text(), nullable=True))

def downgrade() -> None:
    op.drop_column('script_runs', 'token_usage')
    op.drop_column('script_runs', 'prompt_version')
    op.drop_column('script_runs', 'configuration')
    op.drop_column('script_runs', 'model_name')
    op.drop_column('script_runs', 'provider_name')

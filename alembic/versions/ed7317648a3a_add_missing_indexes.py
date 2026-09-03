"""add missing indexes

Revision ID: ed7317648a3a
Revises: da3c6cb48ee2
Create Date: 2026-09-03 22:06:40.898322

"""
from typing import Sequence, Union
import sqlite3
from sqlalchemy.exc import OperationalError

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ed7317648a3a'
down_revision: Union[str, Sequence[str], None] = 'da3c6cb48ee2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def safe_create_index(idx_name, table_name, columns):
    try:
        op.create_index(op.f(idx_name), table_name, columns, unique=False)
    except OperationalError as e:
        if 'already exists' not in str(e).lower():
            raise
        print(f"Skipping index {idx_name}, already exists")

def upgrade() -> None:
    safe_create_index('ix_asset_mappings_source_asset_id', 'asset_mappings', ['source_asset_id'])
    safe_create_index('ix_asset_mappings_visual_intent_id', 'asset_mappings', ['visual_intent_id'])
    safe_create_index('ix_episodes_project_id', 'episodes', ['project_id'])
    safe_create_index('ix_narration_segments_scene_id', 'narration_segments', ['scene_id'])
    safe_create_index('ix_scenes_episode_id', 'scenes', ['episode_id'])
    safe_create_index('ix_visual_intents_narration_segment_id', 'visual_intents', ['narration_segment_id'])

def downgrade() -> None:
    pass

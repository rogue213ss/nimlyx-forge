"""Add V9 Script models

Revision ID: 5dade5238f53
Revises: c336302139ef
Create Date: 2026-09-05 00:40:56.947422

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5dade5238f53'
down_revision: Union[str, Sequence[str], None] = 'c336302139ef'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('script_runs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('story_run_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.Enum('PENDING', 'RUNNING', 'COMPLETED', 'FAILED', name='scriptrunstatus'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['story_run_id'], ['story_runs.id'], name='fk_script_run_story_run'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_script_runs_id'), 'script_runs', ['id'], unique=False)
    
    op.create_table('script_sentences',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('script_run_id', sa.Integer(), nullable=False),
        sa.Column('narration_segment_id', sa.Integer(), nullable=False),
        sa.Column('order_index', sa.Integer(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('original_text', sa.Text(), nullable=False),
        sa.Column('sentence_type', sa.Enum('FACTUAL', 'TRANSITION', 'RHETORICAL', 'DESCRIPTIVE', 'EDITORIAL', name='sentencetype'), nullable=True),
        sa.Column('review_status', sa.Enum('DRAFT', 'NEEDS_REVIEW', 'APPROVED', 'REJECTED', name='reviewstatus'), nullable=True),
        sa.ForeignKeyConstraint(['narration_segment_id'], ['narration_segments.id'], name='fk_sentence_narration'),
        sa.ForeignKeyConstraint(['script_run_id'], ['script_runs.id'], name='fk_sentence_script_run'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_script_sentences_id'), 'script_sentences', ['id'], unique=False)
    
    op.create_table('claim_references',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('script_sentence_id', sa.Integer(), nullable=False),
        sa.Column('research_claim_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['research_claim_id'], ['research_claims.id'], name='fk_claimref_claim'),
        sa.ForeignKeyConstraint(['script_sentence_id'], ['script_sentences.id'], name='fk_claimref_sentence'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_claim_references_id'), 'claim_references', ['id'], unique=False)

def downgrade() -> None:
    op.drop_index(op.f('ix_claim_references_id'), table_name='claim_references')
    op.drop_table('claim_references')
    
    op.drop_index(op.f('ix_script_sentences_id'), table_name='script_sentences')
    op.drop_table('script_sentences')
    
    op.drop_index(op.f('ix_script_runs_id'), table_name='script_runs')
    op.drop_table('script_runs')

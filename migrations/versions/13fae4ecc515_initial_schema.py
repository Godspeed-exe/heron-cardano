"""initial schema

Revision ID: 13fae4ecc515
Revises: 
Create Date: 2025-05-11 10:36:23.619937
"""
from alembic import op # type: ignore
import sqlalchemy as sa # type: ignore


# revision identifiers, used by Alembic.
revision = '13fae4ecc515'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # 1. Create the numeric_id sequence first
    op.execute("CREATE SEQUENCE transaction_numeric_id_seq")

    # 2. Create wallets table
    op.create_table(
        'wallets',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('address', sa.String(), nullable=False),
        sa.Column('encrypted_root_key', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('address')
    )

    # 3. Create transactions table
    op.create_table(
        'transactions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('numeric_id', sa.Integer(), nullable=False,
                  server_default=sa.text("nextval('transaction_numeric_id_seq')")),
        sa.Column('wallet_id', sa.UUID(), nullable=False),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('tx_hash', sa.String(), nullable=True),
        sa.Column('tx_fee', sa.Integer(), nullable=True),
        sa.Column('tx_size', sa.Integer(), nullable=True),
        sa.Column('error_message', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['wallet_id'], ['wallets.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_transactions_numeric_id'), 'transactions', ['numeric_id'], unique=True)

    # 4. Create transaction_outputs table
    op.create_table(
        'transaction_outputs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('transaction_id', sa.Integer(), nullable=False),
        sa.Column('address', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['transaction_id'], ['transactions.numeric_id']),
        sa.PrimaryKeyConstraint('id')
    )

    # 5. Create transaction_output_assets table
    op.create_table(
        'transaction_output_assets',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('output_id', sa.Integer(), nullable=False),
        sa.Column('unit', sa.String(), nullable=False),
        sa.Column('quantity', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['output_id'], ['transaction_outputs.id']),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('transaction_output_assets')
    op.drop_table('transaction_outputs')
    op.drop_index(op.f('ix_transactions_numeric_id'), table_name='transactions')
    op.drop_table('transactions')
    op.drop_table('wallets')
    op.execute("DROP SEQUENCE IF EXISTS transaction_numeric_id_seq")
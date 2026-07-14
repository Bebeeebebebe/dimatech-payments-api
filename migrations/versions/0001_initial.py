"""Initial users, accounts and payments schema with demo data."""

from alembic import op
import sqlalchemy as sa

from app.security import hash_password


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("role IN ('user', 'admin')", name="ck_users_role"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_role", "users", ["role"])

    op.create_table(
        "accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("balance", sa.Numeric(18, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("balance >= 0", name="ck_accounts_non_negative_balance"),
    )
    op.create_index("ix_accounts_user_id", "accounts", ["user_id"])

    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("transaction_id", sa.String(length=128), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_payments_positive_amount"),
        sa.UniqueConstraint("transaction_id"),
    )
    op.create_index("ix_payments_transaction_id", "payments", ["transaction_id"])
    op.create_index("ix_payments_user_id", "payments", ["user_id"])
    op.create_index("ix_payments_account_id", "payments", ["account_id"])

    users = sa.table(
        "users",
        sa.column("id", sa.Integer),
        sa.column("email", sa.String),
        sa.column("full_name", sa.String),
        sa.column("password_hash", sa.String),
        sa.column("role", sa.String),
    )
    op.bulk_insert(
        users,
        [
            {
                "id": 1,
                "email": "user@example.com",
                "full_name": "Test User",
                "password_hash": hash_password("UserPass123!"),
                "role": "user",
            },
            {
                "id": 2,
                "email": "admin@example.com",
                "full_name": "Test Administrator",
                "password_hash": hash_password("AdminPass123!"),
                "role": "admin",
            },
        ],
    )

    accounts = sa.table(
        "accounts",
        sa.column("id", sa.Integer),
        sa.column("user_id", sa.Integer),
        sa.column("balance", sa.Numeric),
    )
    op.bulk_insert(accounts, [{"id": 1, "user_id": 1, "balance": 0}])


def downgrade() -> None:
    op.drop_table("payments")
    op.drop_table("accounts")
    op.drop_table("users")


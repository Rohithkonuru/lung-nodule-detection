"""initial schema

Revision ID: 0001_initial
Revises: 
Create Date: 2026-03-25

"""

from alembic import op
import sqlalchemy as sa


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("email", sa.String(length=256), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("password_hash", sa.String(length=256), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_id"), "users", ["id"], unique=False)

    op.create_table(
        "ct_scans",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("file_name", sa.String(length=512), nullable=False),
        sa.Column("file_path", sa.String(length=1024), nullable=False),
        sa.Column("upload_date", sa.DateTime(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ct_scans_id"), "ct_scans", ["id"], unique=False)
    op.create_index(op.f("ix_ct_scans_owner_id"), "ct_scans", ["owner_id"], unique=False)

    op.create_table(
        "detection_results",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("scan_id", sa.Integer(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("lesion_size", sa.Float(), nullable=True),
        sa.Column("created_date", sa.DateTime(), nullable=False),
        sa.Column("boxes_text", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["scan_id"], ["ct_scans.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_detection_results_id"), "detection_results", ["id"], unique=False)
    op.create_index(op.f("ix_detection_results_scan_id"), "detection_results", ["scan_id"], unique=False)

    op.create_table(
        "clinical_reports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("scan_id", sa.Integer(), nullable=False),
        sa.Column("report_text", sa.Text(), nullable=False),
        sa.Column("created_date", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["scan_id"], ["ct_scans.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_clinical_reports_id"), "clinical_reports", ["id"], unique=False)
    op.create_index(op.f("ix_clinical_reports_scan_id"), "clinical_reports", ["scan_id"], unique=False)

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("entity", sa.String(length=128), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_logs_id"), "audit_logs", ["id"], unique=False)
    op.create_index(op.f("ix_audit_logs_user_id"), "audit_logs", ["user_id"], unique=False)
    op.create_index(op.f("ix_audit_logs_created_at"), "audit_logs", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_audit_logs_created_at"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_user_id"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_id"), table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index(op.f("ix_clinical_reports_scan_id"), table_name="clinical_reports")
    op.drop_index(op.f("ix_clinical_reports_id"), table_name="clinical_reports")
    op.drop_table("clinical_reports")

    op.drop_index(op.f("ix_detection_results_scan_id"), table_name="detection_results")
    op.drop_index(op.f("ix_detection_results_id"), table_name="detection_results")
    op.drop_table("detection_results")

    op.drop_index(op.f("ix_ct_scans_owner_id"), table_name="ct_scans")
    op.drop_index(op.f("ix_ct_scans_id"), table_name="ct_scans")
    op.drop_table("ct_scans")

    op.drop_index(op.f("ix_users_id"), table_name="users")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")

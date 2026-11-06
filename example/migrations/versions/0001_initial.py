"""Initial persistent reference schema, frozen independently of runtime models."""
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
CREATE TABLE login_attempts (
	digest VARCHAR(64) NOT NULL,
	count INTEGER NOT NULL,
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (digest)
)
""")
    op.execute("""
CREATE INDEX ix_login_attempts_expires_at ON login_attempts (expires_at)
""")
    op.execute("""
CREATE TABLE users (
	user_id VARCHAR(32) NOT NULL,
	email VARCHAR(254) NOT NULL,
	password_hash VARCHAR(255) NOT NULL,
	full_name VARCHAR(120) NOT NULL,
	role VARCHAR(16) NOT NULL,
	active BOOLEAN NOT NULL,
	is_verified BOOLEAN NOT NULL,
	PRIMARY KEY (user_id),
	CHECK (role IN ('user', 'admin')),
	UNIQUE (email)
)
""")
    op.execute("""
CREATE TABLE customers (
	customer_id VARCHAR(32) NOT NULL,
	user_id VARCHAR(32) NOT NULL,
	first_name VARCHAR(120) NOT NULL,
	last_name VARCHAR(120) NOT NULL,
	email VARCHAR(254) NOT NULL,
	phone VARCHAR(50),
	date_of_birth VARCHAR(10),
	address JSONB,
	kyc_status VARCHAR(20) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (customer_id),
	UNIQUE (user_id),
	FOREIGN KEY(user_id) REFERENCES users (user_id)
)
""")
    op.execute("""
CREATE INDEX ix_customers_created_at ON customers (created_at)
""")
    op.execute("""
CREATE TABLE notification_events (
	event_id VARCHAR(32) NOT NULL,
	customer_id VARCHAR(32) NOT NULL,
	payload JSONB NOT NULL,
	published BOOLEAN NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (event_id),
	FOREIGN KEY(customer_id) REFERENCES customers (customer_id)
)
""")
    op.execute("""
CREATE INDEX ix_notification_events_published ON notification_events (published)
""")
    op.execute("""
CREATE TABLE verifications (
	verification_id VARCHAR(32) NOT NULL,
	customer_id VARCHAR(32) NOT NULL,
	owner_id VARCHAR(32) NOT NULL,
	idempotency_key VARCHAR(128) NOT NULL,
	verification_type VARCHAR(16) NOT NULL,
	status VARCHAR(20) NOT NULL,
	checks JSONB NOT NULL,
	risk_score INTEGER,
	started_at TIMESTAMP WITH TIME ZONE NOT NULL,
	completed_at TIMESTAMP WITH TIME ZONE,
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (verification_id),
	CONSTRAINT uq_verification_idempotency UNIQUE (owner_id, idempotency_key),
	CHECK (verification_type IN ('standard', 'enhanced')),
	FOREIGN KEY(customer_id) REFERENCES customers (customer_id),
	FOREIGN KEY(owner_id) REFERENCES users (user_id)
)
""")
    op.execute("""
CREATE INDEX ix_verifications_customer_id ON verifications (customer_id)
""")
    op.execute("""
CREATE TABLE websocket_tickets (
	digest VARCHAR(64) NOT NULL,
	user_id VARCHAR(32) NOT NULL,
	customer_id VARCHAR(32) NOT NULL,
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (digest),
	FOREIGN KEY(user_id) REFERENCES users (user_id),
	FOREIGN KEY(customer_id) REFERENCES customers (customer_id)
)
""")
    op.execute("""
CREATE INDEX ix_websocket_tickets_expires_at ON websocket_tickets (expires_at)
""")
    op.execute("""
CREATE TABLE verification_jobs (
	verification_id VARCHAR(32) NOT NULL,
	state VARCHAR(16) NOT NULL,
	attempts INTEGER NOT NULL,
	available_at TIMESTAMP WITH TIME ZONE NOT NULL,
	lease_until TIMESTAMP WITH TIME ZONE,
	lease_token VARCHAR(32),
	PRIMARY KEY (verification_id),
	CHECK (state IN ('pending', 'running', 'done', 'failed')),
	FOREIGN KEY(verification_id) REFERENCES verifications (verification_id)
)
""")
    op.execute("""
CREATE INDEX ix_verification_jobs_available_at ON verification_jobs (available_at)
""")
    op.execute("""
CREATE INDEX ix_verification_jobs_state ON verification_jobs (state)
""")


def downgrade():
    raise RuntimeError("Restore/rollback must use the documented data-preserving procedure")

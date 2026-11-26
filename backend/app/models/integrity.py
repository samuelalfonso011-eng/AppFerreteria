from app.extensions import db
from app.utils.timeutils import iso, utcnow


class LedgerEntry(db.Model):
    __tablename__ = "integrity_ledger"
    __table_args__ = (
        db.Index("ix_integrity_entity", "entity_type", "entity_id"),
        db.CheckConstraint("seq_no > 0 AND entity_id > 0"),
        db.CheckConstraint("entity_type IN ('invoice','payment')"),
        db.CheckConstraint("event_type IN ('issued','voided','payment_recorded','adjustment')"),
    )

    id = db.Column(db.BigInteger().with_variant(db.Integer, "sqlite"), primary_key=True)
    seq_no = db.Column(db.BigInteger, unique=True, nullable=False)
    entity_type = db.Column(db.String(10), nullable=False)
    entity_id = db.Column(db.Integer, nullable=False)
    event_type = db.Column(db.String(20), nullable=False)
    canonical_payload = db.Column(db.Text, nullable=False)
    prev_hash = db.Column(db.String(64), nullable=False)
    current_hash = db.Column(db.String(64), nullable=False, unique=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    def summary(self):
        return dict(seq_no=self.seq_no, entity_type=self.entity_type, entity_id=self.entity_id,
                    event_type=self.event_type, prev_hash=self.prev_hash, current_hash=self.current_hash,
                    hash_short=self.current_hash[:12], created_at=iso(self.created_at))


class Verification(db.Model):
    __tablename__ = "integrity_verifications"
    __table_args__ = (db.CheckConstraint("status IN ('valid','compromised')"),)

    id = db.Column(db.BigInteger().with_variant(db.Integer, "sqlite"), primary_key=True)
    checked_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    checked_by = db.Column(db.String(40), nullable=False)
    status = db.Column(db.String(12), nullable=False)
    total_records_checked = db.Column(db.BigInteger, nullable=False)
    first_broken_seq_no = db.Column(db.BigInteger)
    first_broken_entity_type = db.Column(db.String(10))
    first_broken_entity_id = db.Column(db.Integer)
    failure_reason = db.Column(db.String(32))
    details = db.Column(db.JSON, nullable=False, default=dict)

    def to_dict(self):
        return {**{key: getattr(self, key) for key in (
            "id", "checked_by", "status", "total_records_checked", "first_broken_seq_no",
            "first_broken_entity_type", "first_broken_entity_id", "failure_reason", "details",
        )}, "checked_at": iso(self.checked_at)}

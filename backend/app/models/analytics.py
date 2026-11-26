from sqlalchemy.dialects.postgresql import JSONB

from app.extensions import db
from app.utils.timeutils import iso, utcnow

JSON_DATA = db.JSON().with_variant(JSONB(), "postgresql")


class QualityRun(db.Model):
    __tablename__ = "data_quality_runs"
    __table_args__ = (db.CheckConstraint("quality_score BETWEEN 0 AND 100"),)
    id = db.Column(db.Integer, primary_key=True)
    executed_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    executed_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    total_records_scanned = db.Column(db.Integer, nullable=False)
    issues_found = db.Column(db.Integer, nullable=False)
    auto_fixed_count = db.Column(db.Integer, nullable=False)
    pending_review_count = db.Column(db.Integer, nullable=False)
    quality_score = db.Column(db.Numeric(5, 2), nullable=False)
    summary_by_module = db.Column(JSON_DATA, nullable=False)
    issues = db.relationship("QualityIssue", order_by="QualityIssue.id")

    def report(self):
        return {**{key: getattr(self, key) for key in ("id", "executed_by", "total_records_scanned",
                "issues_found", "auto_fixed_count", "pending_review_count", "summary_by_module")},
                "executed_at": iso(self.executed_at), "quality_score": float(self.quality_score),
                "issues": [issue.report() for issue in self.issues]}


class QualityIssue(db.Model):
    __tablename__ = "data_quality_issues"
    __table_args__ = (
        db.CheckConstraint("module IN ('users','categories','products','orders','invoices','payments')"),
        db.CheckConstraint("issue_type IN ('duplicate_candidate','inconsistent_category','invalid_price',"
                           "'malformed_string','missing_field')"),
        db.CheckConstraint("severity IN ('low','medium','high')"),
        db.CheckConstraint("status IN ('auto_fixed','pending_review','resolved')"),
    )
    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, db.ForeignKey("data_quality_runs.id"), nullable=False, index=True)
    module = db.Column(db.String(16), nullable=False)
    entity_id = db.Column(db.Integer, nullable=False)
    issue_type = db.Column(db.String(24), nullable=False)
    severity = db.Column(db.String(8), nullable=False)
    status = db.Column(db.String(16), nullable=False)
    original_value = db.Column(db.Text)
    normalized_value = db.Column(db.Text)
    details = db.Column(JSON_DATA, nullable=False)

    def report(self):
        return {column.name: getattr(self, column.name) for column in self.__table__.columns}


class AnomalyAlert(db.Model):
    __tablename__ = "anomaly_alerts"
    __table_args__ = (
        db.UniqueConstraint("user_id", "user_role", "alert_type"),
        db.CheckConstraint("user_role IN ('customer','employee')"),
        db.CheckConstraint("alert_type IN ('high_amount_outlier','excessive_cancellations',"
                           "'abusive_discounts','unusual_frequency')"),
        db.CheckConstraint("anomaly_score BETWEEN 0 AND 100"),
    )
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    user_role = db.Column(db.String(12), nullable=False)
    alert_type = db.Column(db.String(32), nullable=False)
    anomaly_score = db.Column(db.Numeric(5, 2), nullable=False)
    threshold_info = db.Column(JSON_DATA, nullable=False)
    explanation = db.Column(db.Text, nullable=False)
    source_record_ids = db.Column(JSON_DATA, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    def report(self):
        return {**{k: getattr(self, k) for k in ("id", "user_id", "user_role", "alert_type", "threshold_info",
                "explanation", "source_record_ids")}, "anomaly_score": float(self.anomaly_score),
                "created_at": iso(self.created_at)}

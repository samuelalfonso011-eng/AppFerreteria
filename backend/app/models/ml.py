from app.extensions import db
from app.models.analytics import JSON_DATA
from app.utils.timeutils import iso, utcnow


class ModelRun(db.Model):
    __tablename__ = "ml_model_runs"
    __table_args__ = (
        db.UniqueConstraint("model_name", "version"),
        db.CheckConstraint("model_name IN ('fraud_classifier','demand_regressor')"),
    )
    id = db.Column(db.Integer, primary_key=True)
    model_name = db.Column(db.String(32), nullable=False)
    version = db.Column(db.String(32), nullable=False)
    trained_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    artifact_path = db.Column(db.Text, nullable=False)
    seed = db.Column(db.Integer, nullable=False)
    dataset_summary = db.Column(JSON_DATA, nullable=False)
    metrics = db.Column(JSON_DATA, nullable=False)

    def summary(self):
        return dict(
            id=self.id,
            model_name=self.model_name,
            version=self.version,
            trained_at=iso(self.trained_at),
            artifact_path=self.artifact_path,
            seed=self.seed,
            dataset_summary=self.dataset_summary,
            metrics=self.metrics,
        )


class FraudPrediction(db.Model):
    __tablename__ = "fraud_predictions"
    __table_args__ = (
        db.CheckConstraint("fraud_probability BETWEEN 0 AND 1"),
        db.CheckConstraint("predicted_label IN ('normal','fraudulenta')"),
    )
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), index=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey("invoices.id"), index=True)
    payment_id = db.Column(db.Integer, db.ForeignKey("payments.id"), index=True)
    model_run_id = db.Column(db.Integer, db.ForeignKey("ml_model_runs.id"), nullable=False, index=True)
    fraud_probability = db.Column(db.Float, nullable=False)
    predicted_label = db.Column(db.String(12), nullable=False)
    feature_snapshot = db.Column(JSON_DATA, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

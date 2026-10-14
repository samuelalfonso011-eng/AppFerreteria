from flask import Blueprint, render_template, redirect, url_for, flash
from app.decorators import admin_required
from app.extensions import db
from app.models.setting import StoreSetting
from app.forms.admin_forms import StoreSettingForm

admin_settings_bp = Blueprint('admin_settings', __name__, url_prefix='/admin/configuracion')


@admin_settings_bp.route('/', methods=['GET', 'POST'])
@admin_required
def index():
    """Configuración comercial e institucional de la ferretería."""
    setting = StoreSetting.get_settings()
    form = StoreSettingForm(obj=setting)

    if form.validate_on_submit():
        setting.store_name = form.store_name.data.strip()
        setting.phone = form.phone.data.strip()
        setting.email = form.email.data.strip()
        setting.address = form.address.data.strip()
        setting.business_hours = form.business_hours.data.strip()
        setting.default_shipping_cost = form.default_shipping_cost.data
        setting.free_shipping_threshold = form.free_shipping_threshold.data

        db.session.commit()
        flash("Configuración comercial guardada correctamente.", "success")
        return redirect(url_for('admin_settings.index'))

    return render_template('admin/settings/settings.html', form=form, setting=setting)

"""Export-Routen für Excel-Downloads"""
from datetime import datetime
from flask import Blueprint, send_file, flash, redirect, url_for
from flask_login import login_required, current_user
from app.models import SchoolYear, SchoolClass
from app.export import export_full_backup, export_full_backup_zip, export_class_list, export_payment_list

export_bp = Blueprint('export', __name__, url_prefix='/export')


@export_bp.route('/backup')
@login_required
def backup():
    """Komplettes Backup als ZIP (Excel + JSON)"""
    active_year = SchoolYear.query.filter_by(is_active=True).first()
    
    if not active_year:
        flash('Kein aktives Schuljahr vorhanden.', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        output = export_full_backup_zip(active_year)
        filename = f"keyboard_backup_{active_year.name.replace('/', '-')}_{datetime.now().strftime('%Y%m%d')}.zip"
        
        return send_file(
            output,
            mimetype='application/zip',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        flash(f'Fehler beim Export: {str(e)}', 'error')
        return redirect(url_for('main.dashboard'))


@export_bp.route('/class/<int:id>')
@login_required
def class_list(id):
    """Klassenliste als Excel"""
    school_class = SchoolClass.query.get_or_404(id)
    
    try:
        output = export_class_list(school_class)
        filename = f"klasse_{school_class.name}_{datetime.now().strftime('%Y%m%d')}.xlsx"
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        flash(f'Fehler beim Export: {str(e)}', 'error')
        return redirect(url_for('classes.detail', id=id))


@export_bp.route('/payments')
@login_required
def payments():
    """Gebühren-Übersicht als Excel"""
    active_year = SchoolYear.query.filter_by(is_active=True).first()
    
    if not active_year:
        flash('Kein aktives Schuljahr vorhanden.', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        output = export_payment_list(active_year)
        filename = f"gebuehren_{active_year.name.replace('/', '-')}_{datetime.now().strftime('%Y%m%d')}.xlsx"
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        flash(f'Fehler beim Export: {str(e)}', 'error')
        return redirect(url_for('main.dashboard'))

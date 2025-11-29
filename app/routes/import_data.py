"""Import-Route für Daten aus Excel/JSON"""
import json
from datetime import date
from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from app.models import db, SchoolYear, SchoolClass, Student, Keyboard, Loan, AuditLog

import_bp = Blueprint('import_data', __name__, url_prefix='/import')


def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin():
            flash('Keine Berechtigung.', 'error')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function


@import_bp.route('/', methods=['GET', 'POST'])
@login_required
@admin_required
def import_json():
    """Import aus JSON-Datei (generiert aus Excel)"""
    
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('Keine Datei ausgewählt.', 'error')
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash('Keine Datei ausgewählt.', 'error')
            return redirect(request.url)
        
        if not file.filename.endswith('.json'):
            flash('Bitte eine JSON-Datei hochladen.', 'error')
            return redirect(request.url)
        
        try:
            data = json.load(file)
            result = do_import(data)
            flash(f'Import erfolgreich! {result}', 'success')
            
            # Audit Log
            log = AuditLog(
                user_id=current_user.id,
                action='import_data',
                entity_type='system',
                details=result,
                ip_address=request.remote_addr
            )
            db.session.add(log)
            db.session.commit()
            
            return redirect(url_for('main.dashboard'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Fehler beim Import: {str(e)}', 'error')
            return redirect(request.url)
    
    return render_template('import/index.html')


def do_import(data):
    """Führt den eigentlichen Import durch"""
    stats = {'keyboards': 0, 'classes': 0, 'students': 0, 'loans': 0}
    
    # Version erkennen
    export_version = data.get('export_version', '1.0')
    
    # 1. Schuljahr anlegen oder finden
    if export_version == '2.0':
        # Neues Format
        year_data = data.get('school_year', {})
        year_name = year_data.get('name', '2024/2025')
        year_start = date.fromisoformat(year_data['start_date']) if year_data.get('start_date') else date(2024, 8, 1)
        year_end = date.fromisoformat(year_data['end_date']) if year_data.get('end_date') else date(2025, 7, 31)
    else:
        # Altes Format
        year_name = data.get('school_year', '2024/2025')
        year_start = date(2024, 8, 1)
        year_end = date(2025, 7, 31)
    
    school_year = SchoolYear.query.filter_by(name=year_name).first()
    if not school_year:
        school_year = SchoolYear(
            name=year_name,
            start_date=year_start,
            end_date=year_end,
            is_active=True
        )
        # Andere Schuljahre deaktivieren
        SchoolYear.query.update({SchoolYear.is_active: False})
        db.session.add(school_year)
        db.session.flush()
    
    # 2. Keyboards importieren
    keyboard_map = {}  # inventory_number -> Keyboard object
    for kb_data in data.get('keyboards', []):
        inv_nr = str(kb_data['inventory_number'])
        
        # Prüfen ob schon existiert
        kb = Keyboard.query.filter_by(inventory_number=inv_nr).first()
        if not kb:
            kb = Keyboard(
                inventory_number=inv_nr,
                internal_number=kb_data.get('internal_number'),
                condition=kb_data.get('condition', 'in_ordnung'),
                status=kb_data.get('status', 'im_lager'),
                notes=kb_data.get('notes')
            )
            db.session.add(kb)
            stats['keyboards'] += 1
        
        keyboard_map[inv_nr] = kb
    
    db.session.flush()
    
    # 3. Klassen importieren
    class_map = {}  # class_name -> SchoolClass object
    for cls_data in data.get('classes', []):
        cls_name = cls_data['name']
        
        # Prüfen ob schon existiert
        cls = SchoolClass.query.filter_by(
            name=cls_name, 
            school_year_id=school_year.id
        ).first()
        
        if not cls:
            cls = SchoolClass(
                name=cls_name,
                grade=cls_data['grade'],
                school_year_id=school_year.id,
                class_teacher=cls_data.get('class_teacher'),
                music_teacher=cls_data.get('music_teacher')
            )
            db.session.add(cls)
            stats['classes'] += 1
        
        class_map[cls_name] = cls
        
        # Schüler aus Klassen-Daten importieren (neues Format v2.0)
        if export_version == '2.0' and 'students' in cls_data:
            db.session.flush()  # cls.id verfügbar machen
            
            for student_data in cls_data['students']:
                # Prüfen ob Schüler schon existiert
                student = Student.query.filter_by(
                    last_name=student_data['last_name'],
                    first_name=student_data['first_name'],
                    class_id=cls.id
                ).first()
                
                if not student:
                    student = Student(
                        last_name=student_data['last_name'],
                        first_name=student_data['first_name'],
                        class_id=cls.id,
                        notes=student_data.get('notes'),
                        participates_in_loan=student_data.get('participates_in_loan', False),
                        fee_prepaid=student_data.get('fee_prepaid', False)
                    )
                    db.session.add(student)
                    stats['students'] += 1
    
    db.session.flush()
    
    # 4. Ausleihen importieren (neues Format v2.0)
    if export_version == '2.0' and 'loans' in data:
        for loan_data in data['loans']:
            cls_name = loan_data['student_class']
            if cls_name not in class_map:
                continue
            
            cls = class_map[cls_name]
            
            # Schüler finden
            student = Student.query.filter_by(
                last_name=loan_data['student_last_name'],
                first_name=loan_data['student_first_name'],
                class_id=cls.id
            ).first()
            
            if not student:
                continue
            
            # Keyboard finden
            kb_inv = loan_data['keyboard_inventory_number']
            if kb_inv not in keyboard_map:
                continue
            
            kb = keyboard_map[kb_inv]
            
            # Prüfen ob schon eine aktive Ausleihe existiert
            existing_loan = Loan.query.filter_by(
                student_id=student.id,
                returned_at=None
            ).first()
            
            if not existing_loan:
                loan = Loan(
                    keyboard_id=kb.id,
                    student_id=student.id,
                    fee_paid=loan_data.get('fee_paid', False),
                    fee_amount=loan_data.get('fee_amount', 10.0)
                )
                db.session.add(loan)
                
                # Keyboard-Status aktualisieren
                kb.status = 'ausgeliehen'
                
                stats['loans'] += 1
    
    # 4b. Altes Format: Schüler separat importieren
    if export_version != '2.0':
        for student_data in data.get('students', []):
            cls_name = student_data['class_name']
            if cls_name not in class_map:
                continue
            
            cls = class_map[cls_name]
            
            # Prüfen ob Schüler schon existiert
            student = Student.query.filter_by(
                last_name=student_data['last_name'],
                first_name=student_data['first_name'],
                class_id=cls.id
            ).first()
            
            if not student:
                student = Student(
                    last_name=student_data['last_name'],
                    first_name=student_data['first_name'],
                    class_id=cls.id,
                    participates_in_loan=student_data.get('participates', False)
                )
                db.session.add(student)
                db.session.flush()
                stats['students'] += 1
            
            # Ausleihe erstellen wenn Keyboard zugewiesen
            keyboard_nr = student_data.get('keyboard_nr')
            if keyboard_nr and keyboard_nr in keyboard_map:
                kb = keyboard_map[keyboard_nr]
                
                # Prüfen ob schon eine aktive Ausleihe existiert
                existing_loan = Loan.query.filter_by(
                    student_id=student.id,
                    returned_at=None
                ).first()
                
                if not existing_loan:
                    loan = Loan(
                        keyboard_id=kb.id,
                        student_id=student.id,
                        fee_paid=False,
                        fee_amount=10.0
                    )
                    db.session.add(loan)
                    
                    # Keyboard-Status aktualisieren
                    kb.status = 'ausgeliehen'
                    
                    stats['loans'] += 1
    
    db.session.commit()
    
    return f"{stats['keyboards']} Keyboards, {stats['classes']} Klassen, {stats['students']} Schüler, {stats['loans']} Ausleihen"

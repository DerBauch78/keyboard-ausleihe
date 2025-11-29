import csv
import io
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, Response
from flask_login import login_required, current_user
from app import db
from app.models import Student, SchoolClass, SchoolYear, Loan

students_bp = Blueprint('students', __name__, url_prefix='/students')


@students_bp.route('/')
@login_required
def index():
    class_filter = request.args.get('class_id', '')
    
    active_year = SchoolYear.query.filter_by(is_active=True).first()
    classes = active_year.classes.order_by(SchoolClass.name).all() if active_year else []
    
    query = Student.query.join(SchoolClass)
    if class_filter:
        query = query.filter(Student.class_id == int(class_filter))
    elif active_year:
        query = query.filter(SchoolClass.school_year_id == active_year.id)
    
    students = query.order_by(SchoolClass.name, Student.last_name, Student.first_name).all()
    
    return render_template('students/index.html',
        students=students,
        classes=classes,
        class_filter=class_filter
    )


@students_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    if not current_user.can_edit():
        flash('Keine Berechtigung.', 'error')
        return redirect(url_for('students.index'))
    
    active_year = SchoolYear.query.filter_by(is_active=True).first()
    classes = active_year.classes.order_by(SchoolClass.name).all() if active_year else []
    
    if request.method == 'POST':
        last_name = request.form.get('last_name', '').strip()
        first_name = request.form.get('first_name', '').strip()
        class_id = request.form.get('class_id')
        notes = request.form.get('notes', '').strip()
        
        if not last_name or not first_name or not class_id:
            flash('Name und Klasse sind erforderlich.', 'error')
            return render_template('students/form.html', student=None, classes=classes)
        
        student = Student(
            last_name=last_name,
            first_name=first_name,
            class_id=int(class_id),
            notes=notes or None
        )
        db.session.add(student)
        db.session.commit()
        
        flash(f'Schüler {last_name}, {first_name} wurde angelegt.', 'success')
        return redirect(url_for('students.index', class_id=class_id))
    
    return render_template('students/form.html', student=None, classes=classes)


@students_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id):
    if not current_user.can_edit():
        flash('Keine Berechtigung.', 'error')
        return redirect(url_for('students.index'))
    
    student = Student.query.get_or_404(id)
    active_year = SchoolYear.query.filter_by(is_active=True).first()
    classes = active_year.classes.order_by(SchoolClass.name).all() if active_year else []
    
    if request.method == 'POST':
        student.last_name = request.form.get('last_name', student.last_name).strip()
        student.first_name = request.form.get('first_name', student.first_name).strip()
        student.class_id = int(request.form.get('class_id', student.class_id))
        student.notes = request.form.get('notes', '').strip() or None
        
        db.session.commit()
        flash('Schüler wurde aktualisiert.', 'success')
        return redirect(url_for('students.index', class_id=student.class_id))
    
    return render_template('students/form.html', student=student, classes=classes)


@students_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    if not current_user.is_admin():
        flash('Nur Administratoren können Schüler löschen.', 'error')
        return redirect(url_for('students.index'))
    
    student = Student.query.get_or_404(id)
    
    if student.loans.filter(Loan.returned_at == None).count() > 0:
        flash('Schüler hat noch ein ausgeliehenes Keyboard.', 'error')
        return redirect(url_for('students.index'))
    
    class_id = student.class_id
    name = student.full_name
    db.session.delete(student)
    db.session.commit()
    
    flash(f'Schüler {name} wurde gelöscht.', 'success')
    return redirect(url_for('students.index', class_id=class_id))


@students_bp.route('/<int:id>/update-notes', methods=['POST'])
@login_required
def update_notes(id):
    """AJAX: Anmerkungen aktualisieren"""
    if not current_user.can_edit():
        return jsonify({'error': 'Keine Berechtigung'}), 403
    
    student = Student.query.get_or_404(id)
    data = request.get_json()
    student.notes = data.get('notes', '').strip() or None
    db.session.commit()
    
    return jsonify({'success': True, 'notes': student.notes})


@students_bp.route('/import', methods=['GET', 'POST'])
@login_required
def import_csv():
    if not current_user.can_edit():
        flash('Keine Berechtigung.', 'error')
        return redirect(url_for('students.index'))
    
    active_year = SchoolYear.query.filter_by(is_active=True).first()
    classes = active_year.classes.order_by(SchoolClass.name).all() if active_year else []
    
    if request.method == 'POST':
        class_id = request.form.get('class_id')
        file = request.files.get('file')
        
        if not class_id or not file:
            flash('Klasse und CSV-Datei sind erforderlich.', 'error')
            return render_template('students/import.html', classes=classes)
        
        try:
            content = file.read().decode('utf-8-sig')
            reader = csv.DictReader(io.StringIO(content), delimiter=';')
            
            imported = 0
            skipped = 0
            errors = []
            
            for i, row in enumerate(reader, start=2):
                try:
                    # Flexible Spaltennamen
                    last_name = row.get('Name') or row.get('Nachname') or row.get('name') or ''
                    first_name = row.get('Vorname') or row.get('vorname') or ''
                    
                    last_name = last_name.strip()
                    first_name = first_name.strip()
                    
                    if not last_name or not first_name:
                        skipped += 1
                        continue
                    
                    # Prüfen ob bereits vorhanden
                    exists = Student.query.filter_by(
                        last_name=last_name,
                        first_name=first_name,
                        class_id=int(class_id)
                    ).first()
                    
                    if exists:
                        skipped += 1
                        continue
                    
                    student = Student(
                        last_name=last_name,
                        first_name=first_name,
                        class_id=int(class_id)
                    )
                    db.session.add(student)
                    imported += 1
                    
                except Exception as e:
                    errors.append(f"Zeile {i}: {str(e)}")
            
            db.session.commit()
            
            msg = f'{imported} Schüler importiert.'
            if skipped > 0:
                msg += f' {skipped} übersprungen.'
            if errors:
                msg += f' {len(errors)} Fehler.'
            
            flash(msg, 'success' if imported > 0 else 'warning')
            
            if errors:
                for error in errors[:5]:
                    flash(error, 'error')
            
            return redirect(url_for('students.index', class_id=class_id))
            
        except Exception as e:
            flash(f'Fehler beim Import: {str(e)}', 'error')
    
    return render_template('students/import.html', classes=classes)


@students_bp.route('/import/template')
@login_required
def download_template():
    csv_content = "Name;Vorname\nMustermann;Max\nMusterfrau;Maria\n"
    return Response(
        csv_content,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=schueler_vorlage.csv'}
    )


@students_bp.route('/api/without-loan')
@login_required
def api_without_loan():
    """API: Schüler ohne aktive Ausleihe für eine Klasse"""
    class_id = request.args.get('class_id')
    if not class_id:
        return jsonify([])
    
    students = Student.query.filter_by(class_id=int(class_id)).all()
    result = []
    for s in students:
        if not s.current_loan:
            result.append({
                'id': s.id,
                'name': s.full_name
            })
    
    return jsonify(sorted(result, key=lambda x: x['name']))


@students_bp.route('/<int:id>/toggle-participation', methods=['POST'])
@login_required
def toggle_participation(id):
    """AJAX: Teilnahme an Ausleihe umschalten"""
    if not current_user.can_edit():
        return jsonify({'error': 'Keine Berechtigung'}), 403
    
    student = Student.query.get_or_404(id)
    student.participates_in_loan = not student.participates_in_loan
    
    # Wenn Teilnahme deaktiviert wird und noch kein Keyboard: fee_paid zurücksetzen
    # (Hat keinen Effekt wenn bereits Ausleihe existiert)
    
    db.session.commit()
    
    return jsonify({
        'success': True, 
        'participates': student.participates_in_loan
    })


@students_bp.route('/<int:id>/toggle-fee-paid', methods=['POST'])
@login_required
def toggle_fee_paid(id):
    """AJAX: Gebühr-Bezahlstatus umschalten (für Schüler ohne Keyboard)"""
    if not current_user.can_edit():
        return jsonify({'error': 'Keine Berechtigung'}), 403
    
    student = Student.query.get_or_404(id)
    
    # Wenn schon eine Ausleihe existiert, dort den Status ändern
    if student.current_loan:
        student.current_loan.fee_paid = not student.current_loan.fee_paid
        fee_paid = student.current_loan.fee_paid
    else:
        # Noch keine Ausleihe - im Student-Model speichern (für späteren Transfer)
        # Wir brauchen ein neues Feld oder nutzen eine "Dummy-Ausleihe"
        # Einfacher: fee_prepaid Feld im Student-Model
        student.fee_prepaid = not getattr(student, 'fee_prepaid', False)
        fee_paid = student.fee_prepaid
    
    db.session.commit()
    
    return jsonify({
        'success': True, 
        'fee_paid': fee_paid
    })

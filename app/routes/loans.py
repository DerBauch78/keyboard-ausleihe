from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Loan, Keyboard, Student, SchoolClass, SchoolYear, AuditLog

loans_bp = Blueprint('loans', __name__, url_prefix='/loans')


@loans_bp.route('/')
@login_required
def index():
    status_filter = request.args.get('status', 'active')
    class_filter = request.args.get('class_id', '')
    
    query = Loan.query.join(Student).join(SchoolClass)
    
    if status_filter == 'active':
        query = query.filter(Loan.returned_at == None)
    elif status_filter == 'returned':
        query = query.filter(Loan.returned_at != None)
    
    if class_filter:
        query = query.filter(Student.class_id == int(class_filter))
    
    loans = query.order_by(Loan.loaned_at.desc()).all()
    
    active_year = SchoolYear.query.filter_by(is_active=True).first()
    classes = active_year.classes.order_by(SchoolClass.name).all() if active_year else []
    
    return render_template('loans/index.html',
        loans=loans,
        classes=classes,
        status_filter=status_filter,
        class_filter=class_filter
    )


@loans_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    if not current_user.can_edit():
        flash('Keine Berechtigung.', 'error')
        return redirect(url_for('loans.index'))
    
    active_year = SchoolYear.query.filter_by(is_active=True).first()
    classes = active_year.classes.filter_by(grade=5).order_by(SchoolClass.name).all() if active_year else []
    
    if request.method == 'POST':
        student_id = request.form.get('student_id')
        keyboard_id = request.form.get('keyboard_id')
        fee_paid = request.form.get('fee_paid') == 'on'
        
        if not student_id or not keyboard_id:
            flash('Schüler und Keyboard müssen ausgewählt werden.', 'error')
            return render_template('loans/form.html', classes=classes)
        
        student = Student.query.get(student_id)
        keyboard = Keyboard.query.get(keyboard_id)
        
        if not student or not keyboard:
            flash('Ungültige Auswahl.', 'error')
            return render_template('loans/form.html', classes=classes)
        
        if student.current_loan:
            flash('Schüler hat bereits ein Keyboard.', 'error')
            return render_template('loans/form.html', classes=classes)
        
        if not keyboard.is_available:
            flash('Keyboard ist nicht verfügbar.', 'error')
            return render_template('loans/form.html', classes=classes)
        
        loan = Loan(
            student_id=student.id,
            keyboard_id=keyboard.id,
            fee_paid=fee_paid,
            created_by=current_user.id
        )
        keyboard.status = 'ausgeliehen'
        
        db.session.add(loan)
        
        log = AuditLog(
            user_id=current_user.id,
            action='loan_create',
            entity_type='loan',
            details=f"Keyboard {keyboard.inventory_number} an {student.full_name}",
            ip_address=request.remote_addr
        )
        db.session.add(log)
        db.session.commit()
        
        flash(f'Keyboard {keyboard.inventory_number} an {student.full_name} ausgeliehen.', 'success')
        return redirect(url_for('classes.detail', id=student.class_id))
    
    return render_template('loans/form.html', classes=classes)


@loans_bp.route('/<int:id>/return', methods=['GET', 'POST'])
@login_required
def return_keyboard(id):
    if not current_user.can_edit():
        flash('Keine Berechtigung.', 'error')
        return redirect(url_for('loans.index'))
    
    loan = Loan.query.get_or_404(id)
    
    if loan.returned_at:
        flash('Dieses Keyboard wurde bereits zurückgegeben.', 'warning')
        return redirect(url_for('loans.index'))
    
    if request.method == 'POST':
        return_condition = request.form.get('return_condition', 'in_ordnung')
        return_notes = request.form.get('return_notes', '').strip()
        
        loan.returned_at = datetime.utcnow()
        loan.return_condition = return_condition
        loan.return_notes = return_notes or None
        
        keyboard = loan.keyboard
        if return_condition in ['defekt', 'in_reparatur']:
            keyboard.condition = return_condition
            keyboard.status = 'in_reparatur' if return_condition == 'in_reparatur' else 'im_lager'
        else:
            keyboard.condition = 'in_ordnung'
            keyboard.status = 'im_lager'
        
        log = AuditLog(
            user_id=current_user.id,
            action='loan_return',
            entity_type='loan',
            entity_id=loan.id,
            details=f"Keyboard {keyboard.inventory_number} von {loan.student.full_name} zurück",
            ip_address=request.remote_addr
        )
        db.session.add(log)
        db.session.commit()
        
        flash(f'Keyboard {keyboard.inventory_number} wurde zurückgegeben.', 'success')
        return redirect(url_for('classes.detail', id=loan.student.class_id))
    
    return render_template('loans/return.html', loan=loan,
        condition_choices=Keyboard.CONDITION_CHOICES)


@loans_bp.route('/<int:id>/toggle-paid', methods=['POST'])
@login_required
def toggle_paid(id):
    """AJAX: Bezahlstatus umschalten"""
    if not current_user.can_edit():
        return jsonify({'error': 'Keine Berechtigung'}), 403
    
    loan = Loan.query.get_or_404(id)
    loan.fee_paid = not loan.fee_paid
    db.session.commit()
    
    return jsonify({'success': True, 'fee_paid': loan.fee_paid})


@loans_bp.route('/quick-loan', methods=['POST'])
@login_required
def quick_loan():
    """Schnelle Ausleihe aus Klassenansicht"""
    if not current_user.can_edit():
        return jsonify({'error': 'Keine Berechtigung'}), 403
    
    data = request.get_json()
    student_id = data.get('student_id')
    keyboard_id = data.get('keyboard_id')
    
    student = Student.query.get(student_id)
    keyboard = Keyboard.query.get(keyboard_id)
    
    if not student or not keyboard:
        return jsonify({'error': 'Ungültige Auswahl'}), 400
    
    if student.current_loan:
        return jsonify({'error': 'Schüler hat bereits ein Keyboard'}), 400
    
    if not keyboard.is_available:
        return jsonify({'error': 'Keyboard nicht verfügbar'}), 400
    
    # fee_prepaid Status vom Schüler übernehmen
    loan = Loan(
        student_id=student.id,
        keyboard_id=keyboard.id,
        fee_paid=student.fee_prepaid,  # Vorausbezahlung übernehmen
        created_by=current_user.id
    )
    keyboard.status = 'ausgeliehen'
    
    db.session.add(loan)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'loan_id': loan.id,
        'keyboard': keyboard.inventory_number
    })


@loans_bp.route('/quick-return', methods=['POST'])
@login_required
def quick_return():
    """Schnelle Rückgabe aus Klassenansicht"""
    if not current_user.can_edit():
        return jsonify({'error': 'Keine Berechtigung'}), 403
    
    data = request.get_json()
    loan_id = data.get('loan_id')
    condition = data.get('condition', 'in_ordnung')
    
    loan = Loan.query.get(loan_id)
    if not loan:
        return jsonify({'error': 'Ausleihe nicht gefunden'}), 404
    
    if loan.returned_at:
        return jsonify({'error': 'Bereits zurückgegeben'}), 400
    
    loan.returned_at = datetime.utcnow()
    loan.return_condition = condition
    
    keyboard = loan.keyboard
    keyboard.condition = condition
    keyboard.status = 'im_lager' if condition == 'in_ordnung' else 'in_reparatur'
    
    db.session.commit()
    
    return jsonify({'success': True})


@loans_bp.route('/<int:id>/undo-return', methods=['POST'])
@login_required
def undo_return(id):
    """Rückgabe stornieren - Keyboard wieder als ausgeliehen markieren"""
    if not current_user.can_edit():
        flash('Keine Berechtigung.', 'error')
        return redirect(url_for('loans.index'))
    
    loan = Loan.query.get_or_404(id)
    
    if not loan.returned_at:
        flash('Diese Ausleihe ist noch aktiv.', 'warning')
        return redirect(url_for('loans.index'))
    
    # Prüfen ob Keyboard inzwischen neu verliehen wurde
    keyboard = loan.keyboard
    if keyboard.current_loan and keyboard.current_loan.id != loan.id:
        flash(f'Keyboard {keyboard.inventory_number} ist bereits an jemand anderen verliehen.', 'error')
        return redirect(url_for('loans.index'))
    
    # Rückgabe stornieren
    old_return_date = loan.returned_at
    loan.returned_at = None
    loan.return_condition = None
    loan.return_notes = None
    
    keyboard.status = 'ausgeliehen'
    keyboard.condition = 'in_ordnung'  # Zurücksetzen auf Standard
    
    log = AuditLog(
        user_id=current_user.id,
        action='loan_undo_return',
        entity_type='loan',
        entity_id=loan.id,
        details=f"Rückgabe storniert: Keyboard {keyboard.inventory_number} von {loan.student.full_name} "
                f"(ursprüngliche Rückgabe: {old_return_date.strftime('%d.%m.%Y %H:%M')})",
        ip_address=request.remote_addr
    )
    db.session.add(log)
    db.session.commit()
    
    flash(f'Rückgabe storniert! Keyboard {keyboard.inventory_number} ist wieder an {loan.student.full_name} ausgeliehen.', 'success')
    return redirect(url_for('classes.detail', id=loan.student.class_id))


@loans_bp.route('/api/undo-return', methods=['POST'])
@login_required
def api_undo_return():
    """AJAX: Rückgabe stornieren"""
    if not current_user.can_edit():
        return jsonify({'error': 'Keine Berechtigung'}), 403
    
    data = request.get_json()
    loan_id = data.get('loan_id')
    
    loan = Loan.query.get(loan_id)
    if not loan:
        return jsonify({'error': 'Ausleihe nicht gefunden'}), 404
    
    if not loan.returned_at:
        return jsonify({'error': 'Ausleihe ist noch aktiv'}), 400
    
    keyboard = loan.keyboard
    if keyboard.current_loan and keyboard.current_loan.id != loan.id:
        return jsonify({'error': f'Keyboard ist bereits an jemand anderen verliehen'}), 400
    
    loan.returned_at = None
    loan.return_condition = None
    loan.return_notes = None
    
    keyboard.status = 'ausgeliehen'
    keyboard.condition = 'in_ordnung'
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'Keyboard {keyboard.inventory_number} wieder aktiv'
    })

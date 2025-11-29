from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import SchoolClass, SchoolYear, Student, Loan, Keyboard

classes_bp = Blueprint('classes', __name__, url_prefix='/classes')


@classes_bp.route('/')
@login_required
def index():
    """Klassenübersicht mit Trennung 5er (Ausleihe) und 6er (Rückgabe)"""
    active_year = SchoolYear.query.filter_by(is_active=True).first()
    
    classes_5 = []
    classes_6 = []
    
    if active_year:
        classes_5 = SchoolClass.query.filter_by(
            school_year_id=active_year.id, grade=5
        ).order_by(SchoolClass.name).all()
        
        classes_6 = SchoolClass.query.filter_by(
            school_year_id=active_year.id, grade=6
        ).order_by(SchoolClass.name).all()
    
    return render_template('classes/index.html',
        active_year=active_year,
        classes_5=classes_5,
        classes_6=classes_6
    )


@classes_bp.route('/<int:id>')
@login_required
def detail(id):
    """Klassendetails mit Schülerliste, Bezahlstatus und Anmerkungen"""
    school_class = SchoolClass.query.get_or_404(id)
    
    students = Student.query.filter_by(class_id=id).order_by(
        Student.last_name, Student.first_name
    ).all()
    
    # Statistiken
    total_students = len(students)
    with_keyboard = sum(1 for s in students if s.current_loan)
    without_keyboard = total_students - with_keyboard
    
    # Für 5er: Teilnehmer zählen (inkl. die ohne Keyboard)
    participants = sum(1 for s in students if s.participates_in_loan or s.current_loan)
    
    # Gebühren: Bezahlt = Loan.fee_paid ODER Student.fee_prepaid
    fees_paid = sum(1 for s in students if 
        (s.current_loan and s.current_loan.fee_paid) or 
        (not s.current_loan and s.participates_in_loan and s.fee_prepaid)
    )
    # Offen = Teilnehmer ohne bezahlt
    fees_unpaid = sum(1 for s in students if
        (s.current_loan and not s.current_loan.fee_paid) or
        (not s.current_loan and s.participates_in_loan and not s.fee_prepaid)
    )
    
    # Für Rückgabe: Anzahl bereits zurückgegeben
    returned = Loan.query.join(Student).filter(
        Student.class_id == id,
        Loan.returned_at != None
    ).count()
    
    # Verfügbare Keyboards für Ausleihe
    available_keyboards = Keyboard.query.filter_by(
        status='im_lager', condition='in_ordnung'
    ).order_by(Keyboard.internal_number).all()
    
    return render_template('classes/detail.html',
        school_class=school_class,
        students=students,
        total_students=total_students,
        with_keyboard=with_keyboard,
        without_keyboard=without_keyboard,
        participants=participants,
        fees_paid=fees_paid,
        fees_unpaid=fees_unpaid,
        returned=returned,
        available_keyboards=available_keyboards,
        condition_choices=Keyboard.CONDITION_CHOICES
    )


@classes_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    if not current_user.can_edit():
        flash('Keine Berechtigung.', 'error')
        return redirect(url_for('classes.index'))
    
    active_year = SchoolYear.query.filter_by(is_active=True).first()
    if not active_year:
        flash('Bitte zuerst ein aktives Schuljahr anlegen.', 'error')
        return redirect(url_for('admin.school_years'))
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip().upper()
        grade = int(request.form.get('grade', 5))
        class_teacher = request.form.get('class_teacher', '').strip()
        music_teacher = request.form.get('music_teacher', '').strip()
        
        if not name:
            flash('Klassenname ist erforderlich.', 'error')
            return render_template('classes/form.html', school_class=None)
        
        if SchoolClass.query.filter_by(name=name, school_year_id=active_year.id).first():
            flash('Diese Klasse existiert bereits.', 'error')
            return render_template('classes/form.html', school_class=None)
        
        school_class = SchoolClass(
            name=name,
            grade=grade,
            school_year_id=active_year.id,
            class_teacher=class_teacher or None,
            music_teacher=music_teacher or None
        )
        db.session.add(school_class)
        db.session.commit()
        
        flash(f'Klasse {name} wurde angelegt.', 'success')
        return redirect(url_for('classes.index'))
    
    return render_template('classes/form.html', school_class=None)


@classes_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id):
    if not current_user.can_edit():
        flash('Keine Berechtigung.', 'error')
        return redirect(url_for('classes.index'))
    
    school_class = SchoolClass.query.get_or_404(id)
    
    if request.method == 'POST':
        school_class.name = request.form.get('name', school_class.name).strip().upper()
        school_class.grade = int(request.form.get('grade', school_class.grade))
        school_class.class_teacher = request.form.get('class_teacher', '').strip() or None
        school_class.music_teacher = request.form.get('music_teacher', '').strip() or None
        
        db.session.commit()
        flash('Klasse wurde aktualisiert.', 'success')
        return redirect(url_for('classes.index'))
    
    return render_template('classes/form.html', school_class=school_class)


@classes_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    if not current_user.is_admin():
        flash('Nur Administratoren können Klassen löschen.', 'error')
        return redirect(url_for('classes.index'))
    
    school_class = SchoolClass.query.get_or_404(id)
    
    if school_class.students.count() > 0:
        flash('Klasse hat noch Schüler und kann nicht gelöscht werden.', 'error')
        return redirect(url_for('classes.index'))
    
    name = school_class.name
    db.session.delete(school_class)
    db.session.commit()
    
    flash(f'Klasse {name} wurde gelöscht.', 'success')
    return redirect(url_for('classes.index'))

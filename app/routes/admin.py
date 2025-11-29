from datetime import date
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import User, SchoolYear, SchoolClass, AuditLog

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_admin():
            flash('Administrator-Rechte erforderlich.', 'error')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated


@admin_bp.route('/')
@login_required
@admin_required
def index():
    users = User.query.order_by(User.username).all()
    school_years = SchoolYear.query.order_by(SchoolYear.start_date.desc()).all()
    recent_logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(50).all()
    
    return render_template('admin/index.html',
        users=users,
        school_years=school_years,
        recent_logs=recent_logs
    )


# --- Schuljahre ---

@admin_bp.route('/school-years')
@login_required
@admin_required
def school_years():
    years = SchoolYear.query.order_by(SchoolYear.start_date.desc()).all()
    return render_template('admin/school_years.html', years=years)


@admin_bp.route('/school-years/new', methods=['GET', 'POST'])
@login_required
@admin_required
def new_school_year():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        is_active = request.form.get('is_active') == 'on'
        
        if not name or not start_date or not end_date:
            flash('Alle Felder sind erforderlich.', 'error')
            return render_template('admin/school_year_form.html', year=None)
        
        if is_active:
            SchoolYear.query.update({SchoolYear.is_active: False})
        
        year = SchoolYear(
            name=name,
            start_date=date.fromisoformat(start_date),
            end_date=date.fromisoformat(end_date),
            is_active=is_active
        )
        db.session.add(year)
        db.session.commit()
        
        # Standard-Klassen anlegen
        if request.form.get('create_classes') == 'on':
            for grade in [5, 6]:
                for letter in ['A', 'B', 'C', 'D']:
                    cls = SchoolClass(
                        name=f"{grade}{letter}",
                        grade=grade,
                        school_year_id=year.id
                    )
                    db.session.add(cls)
            db.session.commit()
        
        flash(f'Schuljahr {name} wurde angelegt.', 'success')
        return redirect(url_for('admin.school_years'))
    
    return render_template('admin/school_year_form.html', year=None)


@admin_bp.route('/school-years/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_school_year(id):
    year = SchoolYear.query.get_or_404(id)
    
    if request.method == 'POST':
        year.name = request.form.get('name', year.name).strip()
        year.start_date = date.fromisoformat(request.form.get('start_date'))
        year.end_date = date.fromisoformat(request.form.get('end_date'))
        is_active = request.form.get('is_active') == 'on'
        
        if is_active and not year.is_active:
            SchoolYear.query.update({SchoolYear.is_active: False})
        year.is_active = is_active
        
        db.session.commit()
        flash('Schuljahr wurde aktualisiert.', 'success')
        return redirect(url_for('admin.school_years'))
    
    return render_template('admin/school_year_form.html', year=year)


@admin_bp.route('/school-years/<int:id>/activate', methods=['POST'])
@login_required
@admin_required
def activate_school_year(id):
    SchoolYear.query.update({SchoolYear.is_active: False})
    year = SchoolYear.query.get_or_404(id)
    year.is_active = True
    db.session.commit()
    
    flash(f'Schuljahr {year.name} ist jetzt aktiv.', 'success')
    return redirect(url_for('admin.school_years'))


# --- Benutzer ---

@admin_bp.route('/users')
@login_required
@admin_required
def users():
    all_users = User.query.order_by(User.username).all()
    return render_template('admin/users.html', users=all_users)


@admin_bp.route('/users/new', methods=['GET', 'POST'])
@login_required
@admin_required
def new_user():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        display_name = request.form.get('display_name', '').strip()
        role = request.form.get('role', 'teacher')
        
        if not username or not password:
            flash('Benutzername und Passwort sind erforderlich.', 'error')
            return render_template('admin/user_form.html', user=None)
        
        if User.query.filter_by(username=username).first():
            flash('Benutzername existiert bereits.', 'error')
            return render_template('admin/user_form.html', user=None)
        
        user = User(
            username=username,
            email=email or None,
            display_name=display_name or username,
            role=role
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        flash(f'Benutzer {username} wurde angelegt.', 'success')
        return redirect(url_for('admin.users'))
    
    return render_template('admin/user_form.html', user=None)


@admin_bp.route('/users/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(id):
    user = User.query.get_or_404(id)
    
    if request.method == 'POST':
        user.email = request.form.get('email', '').strip() or None
        user.display_name = request.form.get('display_name', '').strip() or user.username
        user.role = request.form.get('role', user.role)
        user.is_active = request.form.get('is_active') == 'on'
        
        new_password = request.form.get('password', '').strip()
        if new_password:
            user.set_password(new_password)
        
        db.session.commit()
        flash('Benutzer wurde aktualisiert.', 'success')
        return redirect(url_for('admin.users'))
    
    return render_template('admin/user_form.html', user=user)


@admin_bp.route('/users/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_user(id):
    user = User.query.get_or_404(id)
    
    if user.id == current_user.id:
        flash('Sie können sich nicht selbst löschen.', 'error')
        return redirect(url_for('admin.users'))
    
    username = user.username
    db.session.delete(user)
    db.session.commit()
    
    flash(f'Benutzer {username} wurde gelöscht.', 'success')
    return redirect(url_for('admin.users'))


# --- Audit Log ---

@admin_bp.route('/audit-log')
@login_required
@admin_required
def audit_log():
    page = request.args.get('page', 1, type=int)
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).paginate(
        page=page, per_page=50, error_out=False
    )
    return render_template('admin/audit_log.html', logs=logs)


# --- Schuljahreswechsel ---

@admin_bp.route('/school-year-transition', methods=['GET', 'POST'])
@login_required
@admin_required
def school_year_transition():
    """Schuljahreswechsel: 5er werden zu 6ern, neue 5er-Klassen"""
    current_year = SchoolYear.query.filter_by(is_active=True).first()
    
    if not current_year:
        flash('Kein aktives Schuljahr vorhanden.', 'error')
        return redirect(url_for('admin.school_years'))
    
    # Statistiken für Vorschau
    classes_5 = SchoolClass.query.filter_by(school_year_id=current_year.id, grade=5).all()
    classes_6 = SchoolClass.query.filter_by(school_year_id=current_year.id, grade=6).all()
    
    # Aktive Ausleihen in 5er-Klassen
    from app.models import Loan, Student
    active_loans_5 = Loan.query.join(Student).join(SchoolClass).filter(
        SchoolClass.school_year_id == current_year.id,
        SchoolClass.grade == 5,
        Loan.returned_at == None
    ).count()
    
    # Noch nicht zurückgegebene Keyboards in 6er-Klassen
    active_loans_6 = Loan.query.join(Student).join(SchoolClass).filter(
        SchoolClass.school_year_id == current_year.id,
        SchoolClass.grade == 6,
        Loan.returned_at == None
    ).count()
    
    if request.method == 'POST':
        new_year_name = request.form.get('new_year_name', '').strip()
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        
        if not new_year_name or not start_date or not end_date:
            flash('Alle Felder sind erforderlich.', 'error')
            return render_template('admin/school_year_transition.html',
                current_year=current_year,
                classes_5=classes_5,
                classes_6=classes_6,
                active_loans_5=active_loans_5,
                active_loans_6=active_loans_6
            )
        
        # Warnung wenn noch 6er-Ausleihen offen
        if active_loans_6 > 0 and not request.form.get('confirm_6_open'):
            flash(f'Achtung: Es gibt noch {active_loans_6} nicht zurückgegebene Keyboards in Jahrgang 6! Bitte bestätigen oder zuerst Rückgaben abschließen.', 'warning')
            return render_template('admin/school_year_transition.html',
                current_year=current_year,
                classes_5=classes_5,
                classes_6=classes_6,
                active_loans_5=active_loans_5,
                active_loans_6=active_loans_6,
                show_confirm=True,
                form_data=request.form
            )
        
        # Neues Schuljahr anlegen
        new_year = SchoolYear(
            name=new_year_name,
            start_date=date.fromisoformat(start_date),
            end_date=date.fromisoformat(end_date),
            is_active=False
        )
        db.session.add(new_year)
        db.session.flush()  # ID generieren
        
        students_moved = 0
        loans_moved = 0
        
        # Für jede 5er-Klasse: 6er-Klasse im neuen Jahr anlegen
        for cls5 in classes_5:
            letter = cls5.name[-1]  # A, B, C, D
            
            # Neue 6er-Klasse
            new_cls6 = SchoolClass(
                name=f"6{letter}",
                grade=6,
                school_year_id=new_year.id,
                class_teacher=cls5.class_teacher,
                music_teacher=cls5.music_teacher
            )
            db.session.add(new_cls6)
            db.session.flush()
            
            # Schüler verschieben
            for student in cls5.students:
                student.class_id = new_cls6.id
                students_moved += 1
                
                # Aktive Ausleihe? Zählen
                if student.current_loan:
                    loans_moved += 1
        
        # Neue leere 5er-Klassen anlegen
        for letter in ['A', 'B', 'C', 'D']:
            new_cls5 = SchoolClass(
                name=f"5{letter}",
                grade=5,
                school_year_id=new_year.id
            )
            db.session.add(new_cls5)
        
        # Altes Schuljahr deaktivieren, neues aktivieren
        current_year.is_active = False
        new_year.is_active = True
        
        # Audit-Log
        log = AuditLog(
            user_id=current_user.id,
            action='school_year_transition',
            entity_type='school_year',
            entity_id=new_year.id,
            details=f"Schuljahreswechsel: {current_year.name} → {new_year.name}. "
                    f"{students_moved} Schüler in 6er-Klassen übernommen, "
                    f"{loans_moved} aktive Ausleihen übertragen.",
            ip_address=request.remote_addr
        )
        db.session.add(log)
        
        db.session.commit()
        
        flash(f'Schuljahreswechsel erfolgreich! {students_moved} Schüler wurden in die neuen 6er-Klassen übernommen, '
              f'{loans_moved} aktive Ausleihen wurden übertragen. Neue 5er-Klassen sind bereit für den Import.', 'success')
        return redirect(url_for('admin.school_years'))
    
    # Vorschlag für nächstes Schuljahr
    import re
    match = re.search(r'(\d{4})/(\d{2,4})', current_year.name)
    if match:
        y1 = int(match.group(1))
        suggested_name = f"{y1+1}/{str(y1+2)[-2:]}"
    else:
        suggested_name = ""
    
    return render_template('admin/school_year_transition.html',
        current_year=current_year,
        classes_5=classes_5,
        classes_6=classes_6,
        active_loans_5=active_loans_5,
        active_loans_6=active_loans_6,
        suggested_name=suggested_name
    )

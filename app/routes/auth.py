from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.models import db, User, AuditLog

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember', False)
        
        if not username or not password:
            flash('Bitte Benutzername und Passwort eingeben.', 'error')
            return render_template('auth/login.html')
        
        # Benutzer prüfen
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password) and user.is_active:
            user.last_login = datetime.utcnow()
            db.session.commit()
            login_user(user, remember=remember)
            
            # Audit Log
            log = AuditLog(
                user_id=user.id,
                action='login',
                entity_type='user',
                entity_id=user.id,
                ip_address=request.remote_addr
            )
            db.session.add(log)
            db.session.commit()
            
            next_page = request.args.get('next')
            return redirect(next_page or url_for('main.dashboard'))
        
        flash('Ungültige Anmeldedaten.', 'error')
    
    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    log = AuditLog(
        user_id=current_user.id,
        action='logout',
        entity_type='user',
        entity_id=current_user.id,
        ip_address=request.remote_addr
    )
    db.session.add(log)
    db.session.commit()
    
    logout_user()
    flash('Sie wurden abgemeldet.', 'info')
    return redirect(url_for('auth.login'))

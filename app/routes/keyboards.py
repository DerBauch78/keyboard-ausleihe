from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Keyboard, Loan, AuditLog
from sqlalchemy import or_

keyboards_bp = Blueprint('keyboards', __name__, url_prefix='/keyboards')


@keyboards_bp.route('/')
@login_required
def index():
    status_filter = request.args.get('status', '')
    condition_filter = request.args.get('condition', '')
    search = request.args.get('q', '').strip()
    sort = request.args.get('sort', 'internal_number')
    order = request.args.get('order', 'asc')
    
    query = Keyboard.query
    
    # Filter
    if status_filter:
        query = query.filter_by(status=status_filter)
    if condition_filter:
        query = query.filter_by(condition=condition_filter)
    
    # Suche
    if search:
        search_term = f'%{search}%'
        query = query.filter(or_(
            Keyboard.inventory_number.ilike(search_term),
            Keyboard.notes.ilike(search_term)
        ))
    
    # Sortierung
    sort_columns = {
        'internal_number': Keyboard.internal_number,
        'inventory_number': Keyboard.inventory_number,
        'status': Keyboard.status,
        'condition': Keyboard.condition
    }
    sort_col = sort_columns.get(sort, Keyboard.internal_number)
    if order == 'desc':
        sort_col = sort_col.desc()
    query = query.order_by(sort_col)
    
    keyboards = query.all()
    
    return render_template('keyboards/index.html',
        keyboards=keyboards,
        status_filter=status_filter,
        condition_filter=condition_filter,
        search=search,
        sort=sort,
        order=order,
        status_choices=Keyboard.STATUS_CHOICES,
        condition_choices=Keyboard.CONDITION_CHOICES
    )


@keyboards_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    if not current_user.can_edit():
        flash('Keine Berechtigung.', 'error')
        return redirect(url_for('keyboards.index'))
    
    if request.method == 'POST':
        inventory_number = request.form.get('inventory_number', '').strip()
        internal_number = request.form.get('internal_number', '').strip()
        condition = request.form.get('condition', 'in_ordnung')
        notes = request.form.get('notes', '').strip()
        
        if not inventory_number:
            flash('Inventarnummer ist erforderlich.', 'error')
            return render_template('keyboards/form.html', keyboard=None,
                condition_choices=Keyboard.CONDITION_CHOICES)
        
        if Keyboard.query.filter_by(inventory_number=inventory_number).first():
            flash('Diese Inventarnummer existiert bereits.', 'error')
            return render_template('keyboards/form.html', keyboard=None,
                condition_choices=Keyboard.CONDITION_CHOICES)
        
        keyboard = Keyboard(
            inventory_number=inventory_number,
            internal_number=int(internal_number) if internal_number else None,
            condition=condition,
            status='im_lager',
            notes=notes or None
        )
        db.session.add(keyboard)
        
        log = AuditLog(
            user_id=current_user.id,
            action='create',
            entity_type='keyboard',
            details=f"Keyboard {inventory_number} angelegt",
            ip_address=request.remote_addr
        )
        db.session.add(log)
        db.session.commit()
        
        keyboard.entity_id = keyboard.id
        db.session.commit()
        
        flash(f'Keyboard {inventory_number} wurde angelegt.', 'success')
        return redirect(url_for('keyboards.index'))
    
    return render_template('keyboards/form.html', keyboard=None,
        condition_choices=Keyboard.CONDITION_CHOICES)


@keyboards_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id):
    if not current_user.can_edit():
        flash('Keine Berechtigung.', 'error')
        return redirect(url_for('keyboards.index'))
    
    keyboard = Keyboard.query.get_or_404(id)
    
    if request.method == 'POST':
        keyboard.inventory_number = request.form.get('inventory_number', keyboard.inventory_number).strip()
        internal_number = request.form.get('internal_number', '').strip()
        keyboard.internal_number = int(internal_number) if internal_number else None
        keyboard.condition = request.form.get('condition', keyboard.condition)
        keyboard.status = request.form.get('status', keyboard.status)
        keyboard.notes = request.form.get('notes', '').strip() or None
        
        db.session.commit()
        flash('Keyboard wurde aktualisiert.', 'success')
        return redirect(url_for('keyboards.index'))
    
    return render_template('keyboards/form.html', keyboard=keyboard,
        condition_choices=Keyboard.CONDITION_CHOICES,
        status_choices=Keyboard.STATUS_CHOICES)


@keyboards_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    if not current_user.is_admin():
        flash('Nur Administratoren können Keyboards löschen.', 'error')
        return redirect(url_for('keyboards.index'))
    
    keyboard = Keyboard.query.get_or_404(id)
    
    if keyboard.loans.filter(Loan.returned_at == None).count() > 0:
        flash('Keyboard ist aktuell ausgeliehen und kann nicht gelöscht werden.', 'error')
        return redirect(url_for('keyboards.index'))
    
    inv = keyboard.inventory_number
    db.session.delete(keyboard)
    db.session.commit()
    
    flash(f'Keyboard {inv} wurde gelöscht.', 'success')
    return redirect(url_for('keyboards.index'))


@keyboards_bp.route('/bulk-create', methods=['GET', 'POST'])
@login_required
def bulk_create():
    if not current_user.is_admin():
        flash('Nur Administratoren können Keyboards in Masse anlegen.', 'error')
        return redirect(url_for('keyboards.index'))
    
    if request.method == 'POST':
        prefix = request.form.get('prefix', 'KB').strip()
        start = int(request.form.get('start', 1))
        count = int(request.form.get('count', 10))
        
        created = 0
        for i in range(start, start + count):
            inv = f"{prefix}{i:03d}"
            if not Keyboard.query.filter_by(inventory_number=inv).first():
                kb = Keyboard(
                    inventory_number=inv,
                    internal_number=i,
                    condition='in_ordnung',
                    status='im_lager'
                )
                db.session.add(kb)
                created += 1
        
        db.session.commit()
        flash(f'{created} Keyboards wurden angelegt.', 'success')
        return redirect(url_for('keyboards.index'))
    
    return render_template('keyboards/bulk_create.html')


@keyboards_bp.route('/api/available')
@login_required
def api_available():
    """API: Verfügbare Keyboards für Ausleihe"""
    keyboards = Keyboard.query.filter_by(status='im_lager', condition='in_ordnung').order_by(Keyboard.internal_number).all()
    return jsonify([{
        'id': k.id,
        'inventory_number': k.inventory_number,
        'internal_number': k.internal_number
    } for k in keyboards])

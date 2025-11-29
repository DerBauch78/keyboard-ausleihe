from flask import Blueprint, render_template
from flask_login import login_required
from app.models import Keyboard, Student, Loan, SchoolYear, SchoolClass

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
@login_required
def dashboard():
    # Aktives Schuljahr
    active_year = SchoolYear.query.filter_by(is_active=True).first()
    
    # Keyboard-Statistiken
    total_keyboards = Keyboard.query.count()
    available = Keyboard.query.filter_by(status='im_lager', condition='in_ordnung').count()
    loaned = Keyboard.query.filter_by(status='ausgeliehen').count()
    defect = Keyboard.query.filter(Keyboard.condition.in_(['defekt', 'in_reparatur'])).count()
    missing = Keyboard.query.filter_by(status='verschollen').count()
    
    # Ausleihe-Statistiken
    active_loans = Loan.query.filter(Loan.returned_at == None).count()
    paid_loans = Loan.query.filter(Loan.returned_at == None, Loan.fee_paid == True).count()
    unpaid_loans = active_loans - paid_loans
    total_fees = active_loans * 10  # 10€ pro Ausleihe
    collected_fees = paid_loans * 10
    
    # Klassen des aktiven Schuljahres
    classes_5 = []
    classes_6 = []
    if active_year:
        classes_5 = SchoolClass.query.filter_by(school_year_id=active_year.id, grade=5).order_by(SchoolClass.name).all()
        classes_6 = SchoolClass.query.filter_by(school_year_id=active_year.id, grade=6).order_by(SchoolClass.name).all()
    
    return render_template('main/dashboard.html',
        active_year=active_year,
        total_keyboards=total_keyboards,
        available=available,
        loaned=loaned,
        defect=defect,
        missing=missing,
        active_loans=active_loans,
        paid_loans=paid_loans,
        unpaid_loans=unpaid_loans,
        total_fees=total_fees,
        collected_fees=collected_fees,
        classes_5=classes_5,
        classes_6=classes_6
    )

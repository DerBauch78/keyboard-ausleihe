from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    password_hash = db.Column(db.String(256), nullable=False)
    display_name = db.Column(db.String(120), nullable=True)
    role = db.Column(db.String(20), default='teacher')  # admin, teacher, readonly
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        if self.password_hash:
            return check_password_hash(self.password_hash, password)
        return False
    
    def is_admin(self):
        return self.role == 'admin'
    
    def can_edit(self):
        return self.role in ['admin', 'teacher']


class SchoolYear(db.Model):
    __tablename__ = 'school_years'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(20), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    is_active = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    classes = db.relationship('SchoolClass', backref='school_year', lazy='dynamic')


class SchoolClass(db.Model):
    __tablename__ = 'school_classes'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(10), nullable=False)
    grade = db.Column(db.Integer, nullable=False)
    school_year_id = db.Column(db.Integer, db.ForeignKey('school_years.id'), nullable=False)
    class_teacher = db.Column(db.String(100), nullable=True)
    music_teacher = db.Column(db.String(100), nullable=True)
    loan_date = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    students = db.relationship('Student', backref='school_class', lazy='dynamic')
    
    @property
    def student_count(self):
        return self.students.count()
    
    @property
    def loan_count(self):
        return Loan.query.join(Student).filter(
            Student.class_id == self.id,
            Loan.returned_at == None
        ).count()
    
    @property
    def paid_count(self):
        return Loan.query.join(Student).filter(
            Student.class_id == self.id,
            Loan.returned_at == None,
            Loan.fee_paid == True
        ).count()
    
    @property
    def returned_count(self):
        return Loan.query.join(Student).filter(
            Student.class_id == self.id,
            Loan.returned_at != None
        ).count()


class Student(db.Model):
    __tablename__ = 'students'
    
    id = db.Column(db.Integer, primary_key=True)
    last_name = db.Column(db.String(100), nullable=False)
    first_name = db.Column(db.String(100), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey('school_classes.id'), nullable=False)
    participates_in_loan = db.Column(db.Boolean, default=False)
    fee_prepaid = db.Column(db.Boolean, default=False)  # Gebühr bezahlt VOR Keyboard-Vergabe
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    loans = db.relationship('Loan', backref='student', lazy='dynamic')
    
    @property
    def full_name(self):
        return f"{self.last_name}, {self.first_name}"
    
    @property
    def current_loan(self):
        return self.loans.filter_by(returned_at=None).first()
    
    @property
    def last_loan(self):
        """Letzte Ausleihe (auch wenn zurückgegeben)"""
        return self.loans.order_by(Loan.loaned_at.desc()).first()
    
    @property
    def current_keyboard(self):
        loan = self.current_loan
        return loan.keyboard if loan else None


class Keyboard(db.Model):
    __tablename__ = 'keyboards'
    
    id = db.Column(db.Integer, primary_key=True)
    inventory_number = db.Column(db.String(20), unique=True, nullable=False)
    internal_number = db.Column(db.Integer, nullable=True)
    condition = db.Column(db.String(20), default='in_ordnung')
    status = db.Column(db.String(20), default='im_lager')
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    loans = db.relationship('Loan', backref='keyboard', lazy='dynamic')
    
    CONDITION_CHOICES = [
        ('in_ordnung', 'In Ordnung'),
        ('defekt', 'Defekt'),
        ('in_reparatur', 'In Reparatur')
    ]
    
    STATUS_CHOICES = [
        ('im_lager', 'Im Lager'),
        ('ausgeliehen', 'Ausgeliehen'),
        ('in_reparatur', 'In Reparatur'),
        ('verschollen', 'Verschollen')
    ]
    
    @property
    def current_loan(self):
        return self.loans.filter_by(returned_at=None).first()
    
    @property
    def is_available(self):
        return self.status == 'im_lager' and self.condition == 'in_ordnung'


class Loan(db.Model):
    __tablename__ = 'loans'
    
    id = db.Column(db.Integer, primary_key=True)
    keyboard_id = db.Column(db.Integer, db.ForeignKey('keyboards.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    loaned_at = db.Column(db.DateTime, default=datetime.utcnow)
    returned_at = db.Column(db.DateTime, nullable=True)
    return_condition = db.Column(db.String(20), nullable=True)
    return_notes = db.Column(db.Text, nullable=True)
    fee_paid = db.Column(db.Boolean, default=False)
    fee_amount = db.Column(db.Float, default=10.0)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    created_by_user = db.relationship('User', foreign_keys=[created_by])
    
    @property
    def is_active(self):
        return self.returned_at is None


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    action = db.Column(db.String(50), nullable=False)
    entity_type = db.Column(db.String(50), nullable=False)
    entity_id = db.Column(db.Integer, nullable=True)
    details = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='audit_logs')

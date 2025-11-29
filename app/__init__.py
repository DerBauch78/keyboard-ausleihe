import os
from flask import Flask
from flask_login import LoginManager
from app.models import db

login_manager = LoginManager()


def create_app():
    app = Flask(__name__, template_folder='templates', static_folder='static')
    
    # Konfiguration
    basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', f'sqlite:///{os.path.join(basedir, "data", "keyboards.db")}')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER'] = os.path.join(basedir, 'uploads')
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
    
    # Extensions initialisieren
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Bitte melden Sie sich an.'
    login_manager.login_message_category = 'info'
    
    from app.models import User
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Blueprints registrieren
    from app.routes.auth import auth_bp
    from app.routes.main import main_bp
    from app.routes.keyboards import keyboards_bp
    from app.routes.students import students_bp
    from app.routes.loans import loans_bp
    from app.routes.admin import admin_bp
    from app.routes.classes import classes_bp
    from app.routes.export import export_bp
    from app.routes.import_data import import_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(keyboards_bp)
    app.register_blueprint(students_bp)
    app.register_blueprint(loans_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(classes_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(import_bp)
    
    # Datenbank erstellen
    with app.app_context():
        os.makedirs(os.path.join(basedir, 'data'), exist_ok=True)
        os.makedirs(os.path.join(basedir, 'uploads'), exist_ok=True)
        db.create_all()
        
        # Default Admin erstellen
        if not User.query.filter_by(username='admin').first():
            admin = User(
                username='admin',
                email='admin@schule.local',
                display_name='Administrator',
                role='admin'
            )
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
    
    return app

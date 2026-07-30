import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy import func
import csv
from io import StringIO, BytesIO

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dpg-d9lf2hvqj5pc738v1n20-a')

# Database configuration - Use PostgreSQL on Render, SQLite locally
database_url = os.environ.get('DATABASE_URL')
if database_url:
    # Fix for Render PostgreSQL
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    print(f"✅ Using PostgreSQL database")
else:
    # Local development with SQLite
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    db_path = os.path.join(data_dir, 'expenses.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    print(f"✅ Using SQLite database at {db_path}")

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,  # Check connection before using
    'pool_recycle': 300,    # Recycle connections every 5 minutes
}

db = SQLAlchemy(app)

# Database Models
class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    budget = db.Column(db.Float, default=0)
    expenses = db.relationship('Expense', backref='category_ref', lazy=True)

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    item_name = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, default=1)
    total = db.Column(db.Float, nullable=False)
    date = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Initialize database with default categories
def init_db():
    with app.app_context():
        try:
            db.create_all()
            print("✅ Database tables created/verified")
            
            # Check if we need to add default categories
            if Category.query.count() == 0:
                default_categories = [
                    ('Fare', 4000),
                    ('Groceries', 5000),
                    ('Cosmetics', 2000),
                    ('Entertainment', 3000),
                    ('Utilities', 2000),
                    ('Other', 1000)
                ]
                
                for name, budget in default_categories:
                    category = Category(name=name, budget=budget)
                    db.session.add(category)
                
                db.session.commit()
                print("✅ Default categories created!")
            else:
                print(f"✅ Database ready with {Category.query.count()} categories")
                
            # Verify expenses count
            expense_count = Expense.query.count()
            print(f"✅ Found {expense_count} expenses in database")
            
        except Exception as e:
            print(f"❌ Database initialization error: {str(e)}")
            db.session.rollback()
            raise

# Call init_db
init_db()

# All your routes here (keep the same as before)
# ... (all the route functions remain the same)

@app.route('/debug/db')
def debug_db():
    """Debug endpoint to check database status"""
    try:
        categories = Category.query.all()
        expenses = Expense.query.all()
        return {
            'database_type': 'PostgreSQL' if os.environ.get('DATABASE_URL') else 'SQLite',
            'category_count': len(categories),
            'expense_count': len(expenses),
            'categories': [{'id': c.id, 'name': c.name, 'budget': c.budget} for c in categories],
            'recent_expenses': [{'id': e.id, 'item': e.item_name, 'total': e.total, 'date': e.date} for e in expenses[:5]]
        }
    except Exception as e:
        return {'error': str(e)}, 500

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5000)
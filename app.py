import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy import func

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'

# Database configuration
database_url = os.environ.get('DATABASE_URL')
if database_url:
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
else:
    # Use SQLite with persistent disk on Render
    data_dir = '/data' if os.path.exists('/data') else os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    db_path = os.path.join(data_dir, 'expenses.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
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

# Initialize database
def init_db():
    with app.app_context():
        db.create_all()
        
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

# Call init_db on startup
with app.app_context():
    init_db()

@app.route('/')
def index():
    """Home page"""
    try:
        total_expenses = Expense.query.count()
        total_amount = db.session.query(func.sum(Expense.total)).scalar() or 0
        categories = Category.query.count()
        current_month = datetime.now().strftime('%Y-%m')
        monthly_spent = db.session.query(func.sum(Expense.total)).filter(
            Expense.date.like(f'{current_month}%')
        ).scalar() or 0
        
        return render_template('index.html',
                             total_expenses=total_expenses,
                             total_amount=float(total_amount),
                             categories=categories,
                             monthly_spent=float(monthly_spent))
    except Exception as e:
        return f"<h1>Error on Home Page</h1><p>{str(e)}</p>"

@app.route('/dashboard')
def dashboard():
    """Dashboard"""
    try:
        categories = Category.query.all()
        current_month = datetime.now().strftime('%Y-%m')
        monthly_data = []
        total_budget = 0
        total_spent = 0
        
        for category in categories:
            monthly_spent = db.session.query(func.sum(Expense.total)).filter(
                Expense.category_id == category.id,
                Expense.date.like(f'{current_month}%')
            ).scalar() or 0
            monthly_spent = float(monthly_spent) if monthly_spent else 0.0
            total_spent += monthly_spent
            total_budget += category.budget
            percentage = (monthly_spent / category.budget * 100) if category.budget > 0 else 0
            
            monthly_data.append({
                'name': category.name,
                'budget': float(category.budget),
                'spent': monthly_spent,
                'remaining': float(category.budget - monthly_spent),
                'percentage': float(min(percentage, 100))
            })
        
        recent_expenses = Expense.query.join(Category).order_by(
            Expense.date.desc(), Expense.created_at.desc()
        ).limit(10).all()
        
        return render_template('dashboard.html',
                             monthly_data=monthly_data,
                             recent_expenses=recent_expenses,
                             total_budget=float(total_budget),
                             total_spent=float(total_spent),
                             current_month=current_month)
    except Exception as e:
        return f"<h1>Error on Dashboard</h1><p>{str(e)}</p>"

@app.route('/add', methods=['GET', 'POST'])
def add_expense():
    """Add expense"""
    categories = Category.query.all()
    
    if request.method == 'POST':
        category_id = request.form.get('category_id')
        item_name = request.form.get('item_name')
        amount = request.form.get('amount')
        quantity = request.form.get('quantity', 1)
        date_str = request.form.get('date', datetime.now().strftime('%Y-%m-%d'))
        
        if not category_id or not item_name or not amount:
            flash('Please fill all required fields', 'error')
            return render_template('add_expense.html', categories=categories, now=datetime.now())
        
        try:
            amount = float(amount)
            quantity = int(quantity)
            total = amount * quantity
            
            expense = Expense(
                category_id=int(category_id),
                item_name=item_name,
                amount=amount,
                quantity=quantity,
                total=total,
                date=date_str
            )
            db.session.add(expense)
            db.session.commit()
            flash('Expense added successfully!', 'success')
            return redirect(url_for('add_expense'))
        except Exception as e:
            flash(f'Error: {str(e)}', 'error')
            db.session.rollback()
    
    return render_template('add_expense.html', categories=categories, now=datetime.now())

@app.route('/expenses')
def view_expenses():
    """View expenses"""
    try:
        expenses = Expense.query.join(Category).order_by(Expense.date.desc()).all()
        categories = Category.query.all()
        total = sum(e.total for e in expenses)
        return render_template('view_expenses.html', 
                             expenses=expenses, 
                             categories=categories,
                             category_filter='All',
                             date_filter='',
                             total=total)
    except Exception as e:
        return f"<h1>Error on Expenses Page</h1><p>{str(e)}</p>"

@app.route('/budgets', methods=['GET', 'POST'])
def manage_budgets():
    """Manage budgets"""
    if request.method == 'POST':
        try:
            for key, value in request.form.items():
                if key.startswith('budget_'):
                    category_id = int(key.split('_')[1])
                    budget = float(value)
                    category = Category.query.get(category_id)
                    if category:
                        category.budget = budget
            db.session.commit()
            flash('Budgets updated successfully!', 'success')
        except Exception as e:
            flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('manage_budgets'))
    
    categories = Category.query.all()
    return render_template('budgets.html', categories=categories)

@app.route('/delete/<int:expense_id>', methods=['POST'])
def delete_expense(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    db.session.delete(expense)
    db.session.commit()
    flash('Expense deleted!', 'success')
    return redirect(url_for('view_expenses'))

@app.route('/clear_all', methods=['POST'])
def clear_all_expenses():
    try:
        Expense.query.delete()
        db.session.commit()
        flash('All expenses cleared!', 'success')
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
    return redirect(url_for('view_expenses'))

@app.route('/debug/health')
def health_check():
    return {
        'status': 'OK',
        'timestamp': datetime.now().isoformat(),
        'database_url': 'Set' if os.environ.get('DATABASE_URL') else 'Not Set'
    }

@app.route('/debug/db')
def debug_db():
    try:
        categories = Category.query.all()
        expenses = Expense.query.all()
        return {
            'category_count': len(categories),
            'expense_count': len(expenses),
            'categories': [c.name for c in categories],
            'recent_expenses': [{'id': e.id, 'item': e.item_name, 'total': e.total} for e in expenses[:5]]
        }
    except Exception as e:
        return {'error': str(e)}, 500

@app.errorhandler(404)
def not_found(error):
    return "<h1>404 - Page Not Found</h1><p>The page you're looking for doesn't exist.</p>", 404

@app.errorhandler(500)
def internal_error(error):
    return f"<h1>500 - Internal Server Error</h1><p>{str(error)}</p>", 500

@app.context_processor
def inject_now():
    return {'now': datetime.now()}

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5000)
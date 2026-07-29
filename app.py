from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
import json
import os
from sqlalchemy import func

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///expenses.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

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
    user_id = db.Column(db.String(100), default='default')

# Initialize database with default categories
def init_db():
    with app.app_context():
        db.create_all()
        
        # Add default categories if they don't exist
        default_categories = [
            ('Fare', 4000),
            ('Groceries', 5000),
            ('Cosmetics', 2000),
            ('Entertainment', 3000),
            ('Utilities', 2000),
            ('Other', 1000)
        ]
        
        for name, budget in default_categories:
            if not Category.query.filter_by(name=name).first():
                category = Category(name=name, budget=budget)
                db.session.add(category)
        
        db.session.commit()

# Routes
@app.route('/')
def index():
    """Home page - redirect to dashboard"""
    return redirect(url_for('dashboard'))

@app.route('/add', methods=['GET', 'POST'])
def add_expense():
    """Add a new expense"""
    categories = Category.query.all()
    
    if request.method == 'POST':
        category_id = request.form.get('category_id')
        item_name = request.form.get('item_name')
        amount = request.form.get('amount')
        quantity = request.form.get('quantity', 1)
        date_str = request.form.get('date', datetime.now().strftime('%Y-%m-%d'))
        
        # Validate
        if not all([category_id, item_name, amount]):
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
            flash(f'Expense added successfully! {item_name} - {total:.2f} KSH', 'success')
            return redirect(url_for('add_expense'))
            
        except ValueError as e:
            flash(f'Invalid input: {str(e)}', 'error')
        except Exception as e:
            flash(f'Error adding expense: {str(e)}', 'error')
            db.session.rollback()
    
    return render_template('add_expense.html', categories=categories, now=datetime.now())

@app.route('/expenses')
def view_expenses():
    """View all expenses with filtering"""
    category_filter = request.args.get('category', 'All')
    date_filter = request.args.get('date', '')
    
    query = Expense.query.join(Category)
    
    if category_filter != 'All':
        query = query.filter(Category.name == category_filter)
    
    if date_filter:
        query = query.filter(Expense.date == date_filter)
    
    expenses = query.order_by(Expense.date.desc()).all()
    categories = Category.query.all()
    
    total = sum(e.total for e in expenses)
    
    return render_template('view_expenses.html', 
                         expenses=expenses, 
                         categories=categories,
                         category_filter=category_filter,
                         date_filter=date_filter,
                         total=total)

@app.route('/dashboard')
def dashboard():
    """Dashboard with summary and charts"""
    categories = Category.query.all()
    
    # Get current month
    current_month = datetime.now().strftime('%Y-%m')
    
    # Calculate monthly totals
    monthly_data = []
    total_budget = 0
    total_spent = 0
    
    for category in categories:
        # Get expenses for this category in current month
        monthly_spent = db.session.query(func.sum(Expense.total)).filter(
            Expense.category_id == category.id,
            Expense.date.like(f'{current_month}%')
        ).scalar() or 0
        
        # Convert to float (handle None)
        monthly_spent = float(monthly_spent) if monthly_spent else 0.0
        
        total_spent += monthly_spent
        total_budget += category.budget
        
        # Calculate percentage
        percentage = (monthly_spent / category.budget * 100) if category.budget > 0 else 0
        
        monthly_data.append({
            'name': category.name,
            'budget': float(category.budget),
            'spent': monthly_spent,
            'remaining': float(category.budget - monthly_spent),
            'percentage': float(min(percentage, 100))  # Cap at 100% for display
        })
    
    # Get recent expenses
    recent_expenses = Expense.query.join(Category).order_by(
        Expense.date.desc(), Expense.created_at.desc()
    ).limit(10).all()
    
    # Debug print (check console)
    print("Monthly Data:", monthly_data)
    
    return render_template('dashboard.html',
                         monthly_data=monthly_data,
                         recent_expenses=recent_expenses,
                         total_budget=float(total_budget),
                         total_spent=float(total_spent),
                         current_month=current_month)

@app.route('/budgets', methods=['GET', 'POST'])
def manage_budgets():
    """Manage category budgets"""
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
            flash(f'Error updating budgets: {str(e)}', 'error')
            db.session.rollback()
        
        return redirect(url_for('manage_budgets'))
    
    categories = Category.query.all()
    return render_template('budgets.html', categories=categories)

@app.route('/api/expenses', methods=['GET', 'POST'])
def api_expenses():
    """REST API endpoint for expenses"""
    if request.method == 'POST':
        data = request.json
        
        try:
            category = Category.query.filter_by(name=data.get('category')).first()
            if not category:
                return jsonify({'error': 'Category not found'}), 404
            
            expense = Expense(
                category_id=category.id,
                item_name=data.get('item_name'),
                amount=float(data.get('amount')),
                quantity=int(data.get('quantity', 1)),
                total=float(data.get('amount')) * int(data.get('quantity', 1)),
                date=data.get('date', datetime.now().strftime('%Y-%m-%d'))
            )
            
            db.session.add(expense)
            db.session.commit()
            
            return jsonify({'message': 'Expense added successfully', 'id': expense.id}), 201
            
        except Exception as e:
            return jsonify({'error': str(e)}), 400
    
    # GET - fetch expenses
    expenses = Expense.query.join(Category).all()
    return jsonify([{
        'id': e.id,
        'category': e.category_ref.name,
        'item_name': e.item_name,
        'amount': e.amount,
        'quantity': e.quantity,
        'total': e.total,
        'date': e.date
    } for e in expenses])

@app.route('/api/budgets', methods=['GET'])
def api_budgets():
    """API endpoint for budgets"""
    categories = Category.query.all()
    return jsonify([{
        'name': c.name,
        'budget': c.budget
    } for c in categories])

@app.route('/delete/<int:expense_id>', methods=['POST'])
def delete_expense(expense_id):
    """Delete an expense"""
    expense = Expense.query.get_or_404(expense_id)
    db.session.delete(expense)
    db.session.commit()
    flash('Expense deleted successfully!', 'success')
    return redirect(url_for('view_expenses'))

@app.route('/clear_all', methods=['POST'])
def clear_all_expenses():
    """Clear all expenses"""
    try:
        Expense.query.delete()
        db.session.commit()
        flash('All expenses cleared!', 'success')
    except Exception as e:
        flash(f'Error clearing expenses: {str(e)}', 'error')
        db.session.rollback()
    
    return redirect(url_for('view_expenses'))

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html'), 500

# Context processor to make datetime available in all templates
@app.context_processor
def inject_now():
    return {'now': datetime.now()}

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
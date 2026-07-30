import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy import func
import csv
from io import StringIO, BytesIO

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-here')

# Database configuration for Render
database_url = os.environ.get('DATABASE_URL')
if database_url:
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
else:
    # Local development with SQLite
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    db_path = os.path.join(data_dir, 'expenses.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'

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

# Initialize database
def init_db():
    with app.app_context():
        db.create_all()
        
        # Add default categories if they don't exist
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

# Call init_db
init_db()

@app.route('/')
def index():
    """Home page - landing page"""
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
        print(f"Index error: {str(e)}")
        return render_template('index.html', 
                             total_expenses=0, 
                             total_amount=0, 
                             categories=0, 
                             monthly_spent=0)

@app.route('/dashboard')
def dashboard():
    """Dashboard with summary and charts"""
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
        print(f"Dashboard error: {str(e)}")
        flash(f'Error loading dashboard: {str(e)}', 'error')
        return render_template('dashboard.html',
                             monthly_data=[],
                             recent_expenses=[],
                             total_budget=0,
                             total_spent=0,
                             current_month=datetime.now().strftime('%Y-%m'))

@app.route('/add', methods=['GET', 'POST'])
def add_expense():
    """Add a new expense"""
    try:
        categories = Category.query.all()
    except:
        categories = []
    
    if request.method == 'POST':
        category_id = request.form.get('category_id')
        item_name = request.form.get('item_name')
        amount = request.form.get('amount')
        quantity = request.form.get('quantity', 1)
        date_str = request.form.get('date', datetime.now().strftime('%Y-%m-%d'))
        
        # Validate
        if not category_id:
            flash('Please select a category', 'error')
            return render_template('add_expense.html', categories=categories, now=datetime.now())
        
        if not item_name:
            flash('Please enter an item name', 'error')
            return render_template('add_expense.html', categories=categories, now=datetime.now())
        
        if not amount:
            flash('Please enter an amount', 'error')
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
    try:
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
    except Exception as e:
        print(f"Expenses error: {str(e)}")
        flash(f'Error loading expenses: {str(e)}', 'error')
        try:
            categories = Category.query.all()
        except:
            categories = []
        return render_template('view_expenses.html', 
                             expenses=[], 
                             categories=categories,
                             category_filter='All',
                             date_filter='',
                             total=0)

@app.route('/add_category', methods=['POST'])
def add_category():
    """Add a new category"""
    category_name = request.form.get('category_name')
    category_budget = request.form.get('category_budget', 0)
    
    if not category_name:
        flash('Please enter a category name', 'error')
        return redirect(url_for('add_expense'))
    
    # Check if category already exists
    existing = Category.query.filter_by(name=category_name).first()
    if existing:
        flash(f'Category "{category_name}" already exists!', 'error')
        return redirect(url_for('add_expense'))
    
    try:
        new_category = Category(name=category_name, budget=float(category_budget))
        db.session.add(new_category)
        db.session.commit()
        flash(f'Category "{category_name}" added successfully!', 'success')
    except Exception as e:
        flash(f'Error adding category: {str(e)}', 'error')
        db.session.rollback()
    
    return redirect(url_for('add_expense'))

@app.route('/edit/<int:expense_id>', methods=['GET', 'POST'])
def edit_expense(expense_id):
    """Edit an existing expense"""
    expense = Expense.query.get_or_404(expense_id)
    categories = Category.query.all()
    
    if request.method == 'POST':
        category_id = request.form.get('category_id')
        item_name = request.form.get('item_name')
        amount = request.form.get('amount')
        quantity = request.form.get('quantity', 1)
        date_str = request.form.get('date')
        
        # Validate
        if not category_id:
            flash('Please select a category', 'error')
            return render_template('edit_expense.html', expense=expense, categories=categories, now=datetime.now())
        
        if not item_name:
            flash('Please enter an item name', 'error')
            return render_template('edit_expense.html', expense=expense, categories=categories, now=datetime.now())
        
        if not amount:
            flash('Please enter an amount', 'error')
            return render_template('edit_expense.html', expense=expense, categories=categories, now=datetime.now())
        
        try:
            expense.category_id = int(category_id)
            expense.item_name = item_name
            expense.amount = float(amount)
            expense.quantity = int(quantity)
            expense.total = float(amount) * int(quantity)
            expense.date = date_str
            
            db.session.commit()
            flash('Expense updated successfully!', 'success')
            return redirect(url_for('view_expenses'))
            
        except ValueError as e:
            flash(f'Invalid input: {str(e)}', 'error')
        except Exception as e:
            flash(f'Error updating expense: {str(e)}', 'error')
            db.session.rollback()
    
    return render_template('edit_expense.html', expense=expense, categories=categories, now=datetime.now())

@app.route('/export_excel')
def export_excel():
    """Export expenses to Excel"""
    try:
        category_filter = request.args.get('category', 'All')
        date_filter = request.args.get('date', '')
        
        query = Expense.query.join(Category)
        
        if category_filter != 'All':
            query = query.filter(Category.name == category_filter)
        
        if date_filter:
            query = query.filter(Expense.date == date_filter)
        
        expenses = query.order_by(Expense.date.desc()).all()
        
        if not expenses:
            flash('No expenses to export!', 'error')
            return redirect(url_for('view_expenses'))
        
        # Try Excel export with pandas
        try:
            import pandas as pd
            
            data = []
            for expense in expenses:
                data.append({
                    'Date': expense.date,
                    'Category': expense.category_ref.name,
                    'Item Name': expense.item_name,
                    'Quantity': expense.quantity,
                    'Amount (KSH)': expense.amount,
                    'Total (KSH)': expense.total
                })
            
            df = pd.DataFrame(data)
            output = BytesIO()
            
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Expenses', index=False)
            
            output.seek(0)
            filename = f"expenses_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            
            return send_file(
                output,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name=filename
            )
        except ImportError:
            # Fallback to CSV if pandas not installed
            return redirect(url_for('export_csv_simple'))
            
    except Exception as e:
        flash(f'Export error: {str(e)}', 'error')
        return redirect(url_for('view_expenses'))

@app.route('/export_csv_simple')
def export_csv_simple():
    """Export expenses to CSV"""
    try:
        category_filter = request.args.get('category', 'All')
        date_filter = request.args.get('date', '')
        
        query = Expense.query.join(Category)
        
        if category_filter != 'All':
            query = query.filter(Category.name == category_filter)
        
        if date_filter:
            query = query.filter(Expense.date == date_filter)
        
        expenses = query.order_by(Expense.date.desc()).all()
        
        if not expenses:
            flash('No expenses to export!', 'error')
            return redirect(url_for('view_expenses'))
        
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(['Date', 'Category', 'Item Name', 'Quantity', 'Amount (KSH)', 'Total (KSH)'])
        
        for expense in expenses:
            writer.writerow([
                expense.date,
                expense.category_ref.name,
                expense.item_name,
                expense.quantity,
                f"{expense.amount:.2f}",
                f"{expense.total:.2f}"
            ])
        
        output.seek(0)
        filename = f"expenses_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        return send_file(
            BytesIO(output.getvalue().encode('utf-8-sig')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        flash(f'Export error: {str(e)}', 'error')
        return redirect(url_for('view_expenses'))

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

@app.route('/debug/expenses')
def debug_expenses():
    """Debug endpoint to check expenses"""
    try:
        expenses = Expense.query.all()
        categories = Category.query.all()
        return {
            'expense_count': len(expenses),
            'category_count': len(categories),
            'expenses': [{'id': e.id, 'item': e.item_name, 'total': e.total} for e in expenses[:5]],
            'categories': [c.name for c in categories]
        }
    except Exception as e:
        return {'error': str(e)}, 500

@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html'), 500

@app.context_processor
def inject_now():
    return {'now': datetime.now()}

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5000)
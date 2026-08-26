import csv
import io

from flask import Flask, flash, render_template, request, url_for, redirect, Response
from flask_sqlalchemy import SQLAlchemy
from datetime import date, datetime
from sqlalchemy import func

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'my_secret_key'

db = SQLAlchemy(app)

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(120), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(120), nullable=False)
    date_created = db.Column(db.Date, default=date.today)

with app.app_context():


    db.create_all()
def parse_date(date_str):
    try:
        return datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return None

@app.route('/')
def index():
    # read query string parameters for filtering
    start_str = request.args.get('start_date', '').strip()
    end_str = request.args.get('end_date', '').strip()
    category_filter = request.args.get('category', '').strip()

    start_date = parse_date(start_str)
    end_date = parse_date(end_str)

    if start_date and end_date and end_date < start_date:
        flash('End date cannot be earlier than start date', 'error')
        start_date = end_date = None
        start_str = end_str = ''

    q = Expense.query
    if start_date:
        q = q.filter(Expense.date_created >= start_date)
    if end_date:
        q = q.filter(Expense.date_created <= end_date)
    if category_filter:
        q = q.filter(Expense.category == category_filter)

    expenses = q.order_by(Expense.date_created.desc()).all()
    total = round(sum(expense.amount for expense in expenses), 2)

# pie chart
    cat_q = db.session.query(Expense.category, func.sum(Expense.amount))
    if start_date:
        cat_q = cat_q.filter(Expense.date_created >= start_date)
    if end_date:
        cat_q = cat_q.filter(Expense.date_created <= end_date)
    if category_filter:
        cat_q = cat_q.filter(Expense.category == category_filter)

    cat_rows = cat_q.group_by(Expense.category).all()
    cat_labels = [c for c, _ in cat_rows]
    cat_values = [round(float(v or 0), 2) for _, v in cat_rows]

    # day chart
    day_q = db.session.query(Expense.date_created, func.sum(Expense.amount))
    if start_date:
        day_q = day_q.filter(Expense.date_created >= start_date)
    if end_date:
        day_q = day_q.filter(Expense.date_created <= end_date)
    if category_filter:
        day_q = day_q.filter(Expense.category == category_filter)

    day_rows = day_q.group_by(Expense.date_created).order_by(Expense.date_created).all()
    day_labels = [d.isoformat() for d, _ in day_rows]
    day_values = [round(float(v or 0), 2) for _, v in day_rows]

    return render_template(
        'index.html',
        today=date.today().isoformat(),
        expenses=expenses,
        total=total,
        start_str=start_str,
        end_str=end_str,
        category_filter=category_filter,
        cat_labels=cat_labels,
        cat_values=cat_values,
        day_labels=day_labels,
        day_values=day_values
    )

@app.route('/add', methods=['POST'])
def add():
    description = (request.form.get('description') or '').strip()
    amount_str = (request.form.get('amount') or '').strip()
    category = (request.form.get('category') or '').strip()
    date_str = (request.form.get('date') or '').strip()

    if not description or not amount_str or not category or not date_str:
        flash('Missing required fields', 'error')
        return redirect(url_for('index'))

    try:
        amount = float(amount_str)
        if amount <= 0:
            flash('Amount must be greater than zero', 'error')
            return redirect(url_for('index'))
    except ValueError:
        flash('Amount must be a valid number', 'error')
        return redirect(url_for('index'))

    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        flash('Date must be a valid date', 'error')
        return redirect(url_for('index'))

    expense = Expense(
        description=description,
        amount=amount,
        category=category,
        date_created=date_obj,
    )

    db.session.add(expense)
    db.session.commit()

    flash('Expense added successfully', 'success')
    return redirect(url_for('index'))
@app.route('/delete/<int:expense_id>', methods=['POST'])
def delete(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    db.session.delete(expense)
    db.session.commit()
    flash('Expense deleted successfully', 'success')
    return redirect(url_for('index'))

@app.route('/edit/<int:expense_id>', methods=['GET'])
def edit(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    categories = ["Food", "Transport", "Rent", "Utilities", "Health", "Entertainment", "Other"]
    return render_template('edit.html', expense=expense, categories=categories, today=date.today().isoformat())

@app.route('/edit/<int:expense_id>', methods=['POST'])
def edit_post(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    description = (request.form.get('description') or '').strip()
    amount_str = (request.form.get('amount') or '').strip()
    category = (request.form.get('category') or '').strip()
    date_str = (request.form.get('date') or '').strip()

    if not description or not amount_str or not category or not date_str:
        flash('Missing required fields', 'error')
        return redirect(url_for('edit', expense_id=expense_id))

    try:
        amount = float(amount_str)
        if amount <= 0:
            flash('Amount must be greater than zero', 'error')
            return redirect(url_for('edit', expense_id=expense_id))
    except ValueError:
        flash('Amount must be a valid number', 'error')
        return redirect(url_for('edit', expense_id=expense_id))

    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        flash('Date must be a valid date', 'error')
        return redirect(url_for('edit', expense_id=expense_id))

    expense.description = description
    expense.amount = amount
    expense.category = category
    expense.date_created = date_obj

    db.session.commit()
    flash('Expense updated successfully', 'success')
    return redirect(url_for('index'))

@app.route("/export.csv")
def export_csv():
    start_str = request.args.get('start_date', '').strip()
    end_str = request.args.get('end_date', '').strip()
    category_filter = request.args.get('category', '').strip()

    start_date = parse_date(start_str)
    end_date = parse_date(end_str)

    q = Expense.query
    if start_date:
        q = q.filter(Expense.date_created >= start_date)
    if end_date:
        q = q.filter(Expense.date_created <= end_date)
    if category_filter:
        q = q.filter(Expense.category == category_filter)

    expenses = q.order_by(Expense.date_created.asc(), Expense.id.asc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Description", "Amount", "Category", "Date"])

    for expense in expenses:
        writer.writerow([
            expense.description,
            f"{expense.amount:.2f}",
            expense.category,
            expense.date_created.isoformat(),
        ])

    csv_data = output.getvalue()
    fname_start = start_str or "all"
    fname_end = end_str or "all"
    filename = f"expenses_{fname_start}_to_{fname_end}.csv"

    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

if __name__ == '__main__':
    app.run(debug=True, port=5000)
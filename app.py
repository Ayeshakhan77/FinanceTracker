from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from datetime import datetime
import sqlite3
from collections import defaultdict

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# SQLite database setup
DATABASE = 'finance_tracker.db'

def init_db():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    # Users table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    # Transactions table
    c.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            date TEXT NOT NULL,
            description TEXT,
            payment_method TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    # Transfers table
    c.execute('''
        CREATE TABLE IF NOT EXISTS transfers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL,
            receiver_id INTEGER NOT NULL,
            amount REAL NOT NULL CHECK(amount > 0),
            description TEXT,
            date TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (sender_id) REFERENCES users (id),
            FOREIGN KEY (receiver_id) REFERENCES users (id)
        )
    ''')
    conn.commit()
    conn.close()

# Initialize database
init_db()

@app.route('/')
def index():
    if 'username' in session:
        user_id = session['user_id']
        username = session['username']
        
        # Fetch transactions
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute("SELECT * FROM transactions WHERE user_id = ?", (user_id,))
        transactions = c.fetchall()
        
        # Summarize transactions
        total_amount = sum(transaction[2] for transaction in transactions)
        total_upi = sum(transaction[2] for transaction in transactions if transaction[6] == 'UPI')
        total_cash = sum(transaction[2] for transaction in transactions if transaction[6] == 'Cash')
        
        conn.close()

        return render_template('index.html', username=username, total_amount=total_amount, total_upi=total_upi, total_cash=total_cash)
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute("SELECT id, username FROM users WHERE username = ? AND password = ?", (username, password))
        user = c.fetchone()
        conn.close()
        if user:
            session['user_id'] = user[0]
            session['username'] = user[1]
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password. Please try again.', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('user_id', None)
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        phone = request.form['phone']
        password = request.form['password']
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username = ?", (username,))
        existing_user = c.fetchone()
        if existing_user:
            flash('Username already exists. Please choose a different one.', 'error')
        else:
            c.execute("INSERT INTO users (username, email, phone, password) VALUES (?, ?, ?, ?)",
                      (username, email, phone, password))
            conn.commit()
            conn.close()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/transactions')
def transactions():
    if 'username' in session:
        user_id = session['user_id']
        username = session['username']
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute("SELECT * FROM transactions WHERE user_id = ?", (user_id,))
        transactions = c.fetchall()
        conn.close()

        return render_template('transaction.html', transactions=transactions, username=username)
    else:
        return redirect(url_for('login'))

@app.route('/add_transaction', methods=['POST'])
def add_transaction():
    if 'username' in session:
        user_id = session['user_id']
        date = request.form['date']
        category = request.form['category']
        amount = float(request.form['amount'])
        payment_method = request.form['payment_method']
        description = request.form['notes']

        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute("INSERT INTO transactions (user_id, date, category, amount, payment_method, description) VALUES (?, ?, ?, ?, ?, ?)",
                  (user_id, date, category, amount, payment_method, description))
        conn.commit()
        conn.close()

        return redirect(url_for('transactions'))
    else:
        return redirect(url_for('login'))

@app.route('/transfer', methods=['GET', 'POST'])
def transfer_money():
    if 'username' in session:
        if request.method == 'POST':
            sender_id = session['user_id']
            receiver_id = int(request.form['receiver_id'])
            amount = float(request.form['amount'])
            description = request.form.get('description', 'Transfer')

            if amount <= 0:
                flash('Transfer amount must be greater than zero.', 'error')
                return redirect(url_for('transfer_money'))

            conn = sqlite3.connect(DATABASE)
            c = conn.cursor()

            # Add transfer record
            c.execute('''
                INSERT INTO transfers (sender_id, receiver_id, amount, description)
                VALUES (?, ?, ?, ?)
            ''', (sender_id, receiver_id, amount, description))

            # Log in transactions table
            c.execute('''
                INSERT INTO transactions (user_id, amount, category, date, description, payment_method)
                VALUES (?, ?, 'Transfer', datetime('now'), ?, 'Transfer')
            ''', (sender_id, -amount, description))
            c.execute('''
                INSERT INTO transactions (user_id, amount, category, date, description, payment_method)
                VALUES (?, ?, 'Transfer', datetime('now'), ?, 'Transfer')
            ''', (receiver_id, amount, description))

            conn.commit()
            conn.close()

            flash('Transfer successful!', 'success')
            return redirect(url_for('transactions'))

        # Fetch users for dropdown
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute("SELECT id, username FROM users WHERE id != ?", (session['user_id'],))
        users = c.fetchall()
        conn.close()

        return render_template('transfer.html', users=users)
    else:
        return redirect(url_for('login'))
    
@app.route('/daily_spending_data')
def daily_spending_data():
    if 'username' in session:
        user_id = session['user_id']
        
        # Fetch daily spending data from the database
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute("SELECT date, SUM(amount) FROM transactions WHERE user_id = ? GROUP BY date", (user_id,))
        data = c.fetchall()
        conn.close()

        # Format data for Chart.js
        labels = [row[0] for row in data]
        amounts = [row[1] for row in data]

        return jsonify({'labels': labels, 'amounts': amounts})
    else:
        return redirect(url_for('login'))

@app.route('/monthly_spending_data')
def monthly_spending_data():
    if 'username' in session:
        user_id = session['user_id']
        
        # Fetch monthly spending data from the database
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute("SELECT strftime('%Y-%m', date) AS month, SUM(amount) FROM transactions WHERE user_id = ? GROUP BY month", (user_id,))
        data = c.fetchall()
        conn.close()

        # Format data for Chart.js
        labels = [datetime.strptime(row[0], '%Y-%m').strftime('%b %Y') for row in data]
        amounts = [row[1] for row in data]

        return jsonify({'labels': labels, 'amounts': amounts})
    else:
        return redirect(url_for('login'))
    

@app.route('/statistics')
def statistics():
    if 'username' in session:
        user_id = session['user_id']
        username = session['username']
        
        # Fetch statistics data (e.g., total expenses, breakdown by category, top categories)
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()

        # Fetch total expenses
        c.execute("SELECT SUM(amount) FROM transactions WHERE user_id = ?", (user_id,))
        total_expenses = c.fetchone()[0] or 0

        # Fetch expense breakdown by category
        c.execute("SELECT category, SUM(amount) FROM transactions WHERE user_id = ? GROUP BY category", (user_id,))
        expense_by_category = dict(c.fetchall())

        # Fetch top spending categories (limit to top N categories)
        c.execute("SELECT category, SUM(amount) FROM transactions WHERE user_id = ? GROUP BY category ORDER BY SUM(amount) DESC LIMIT 5", (user_id,))
        top_spending_categories = dict(c.fetchall())

        conn.close()

        # Pass the data to the template
        return render_template('statistics.html', username=username, 
                               total_expenses=total_expenses, 
                               expense_by_category=expense_by_category, 
                               top_spending_categories=top_spending_categories)
    return redirect(url_for('login'))
    
@app.route('/delete_transaction/<int:transaction_id>', methods=['POST'])
def delete_transaction(transaction_id):
    if 'username' in session:
        user_id = session['user_id']

        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()

        # Delete the transaction
        c.execute("DELETE FROM transactions WHERE id = ? AND user_id = ?", (transaction_id, user_id))
        conn.commit()
        conn.close()

        flash('Transaction deleted successfully!', 'success')
        return redirect(url_for('transactions'))
    else:
        return redirect(url_for('login'))

# The rest of your code remains the same

if __name__ == '__main__':
    app.run(debug=True)

import numpy as np
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import asc, desc, func
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from flask_bootstrap import Bootstrap5
from typing import List
import matplotlib
import matplotlib.pyplot as plt
from matplotlib import dates
import datetime
import calendar

matplotlib.use('Agg')
app = Flask(__name__)
app.secret_key = 'fdsugiowayefgoirewayfugy'
Bootstrap5(app)
db = SQLAlchemy()
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///expense.db"
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
last_updated_date = None


class User(db.Model, UserMixin):
    __tablename__ = 'user'
    id: db.Mapped[int] = db.mapped_column(primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(50), nullable=False)
    monthly_expense = db.Column(db.Integer, default=0)
    monthly_budget = db.Column(db.Integer, default=0)
    total_expense = db.Column(db.Integer, default=0)
    total_goals = db.Column(db.Integer, default=0)
    savings = db.Column(db.Integer, default=0)
    # Relationship
    expense: db.Mapped[List["Expense"]] = db.relationship(back_populates="user")
    goals: db.Mapped[List["Goals"]] = db.relationship(back_populates="user")

    def is_authenticated(self):
        return True

    def is_active(self):
        return True

    def get_id(self):
        return self.id


class Expense(db.Model, UserMixin):
    __table_name__ = 'expenses'
    id: db.Mapped[int] = db.mapped_column(primary_key=True)
    category = db.Column(db.String(50), nullable=False)
    date = db.Column(db.String(20), nullable=False)
    description = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    # Relationship
    user: db.Mapped["User"] = db.relationship(back_populates="expense")
    user_id: db.Mapped[int] = db.mapped_column(db.ForeignKey("user.id"))


class Goals(db.Model, UserMixin):
    __table_name__ = 'goals'
    id: db.Mapped[int] = db.mapped_column(primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    # Relationship
    user: db.Mapped["User"] = db.relationship(back_populates="goals")
    user_id: db.Mapped[int] = db.mapped_column(db.ForeignKey("user.id"))


with app.app_context():
    db.create_all()


def update_savings():
    global last_updated_date

    savings = 0
    date = datetime.datetime.today()
    # date = datetime.datetime.strptime('2024-04-30 09:52:12.993281', '%Y-%m-%d %H:%M:%S.%f')
    # last_updated_date = None

    if last_updated_date == date:
        # If last_updated_date is today, return without updating savings
        return 0

    # Get the last day of the month
    last_day_of_month = calendar.monthrange(date.year, date.month)[1]
    # Check if today is the last day of the month
    if date.day == last_day_of_month:
        # Get current month expense
        current_user.monthly_expense = update_monthly(0, True)
        savings = current_user.monthly_budget - current_user.monthly_expense

    last_updated_date = date
    return savings


def update_monthly(month, this_month):
    if this_month:
        current_user.monthly_expense = 0
        current_date = datetime.date.today()
        month = current_date.month - month
    month_total = 0
    monthly = db.session.execute(db.Select(Expense).where(Expense.user_id == current_user.get_id()).filter(func.extract('month', Expense.date) == month)).scalars()
    for per_month in monthly:
        month_total = month_total + int(per_month.amount)
    return month_total


@login_manager.user_loader
def load_user(user_id):
    return db.session.execute(db.select(User).where(User.id == user_id)).scalar()


@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        new_expense = Expense(
            category=request.form['category'],
            date=request.form['date'],
            description=request.form['description'],
            amount=request.form['amount'],
            user=current_user,
        )
        current_user.total_expense = current_user.total_expense + int(request.form['amount'])
        db.session.add(new_expense)
    current_user.monthly_expense = update_monthly(0, True)
    db.session.commit()
    return render_template('index.html', user=current_user)


@app.route('/set_month_budget', methods=['GET', 'POST'])
def set_month_budget():
    if request.method == 'POST':
        current_user.monthly_budget = request.form['budget']
        db.session.commit()

    return render_template('index.html', user=current_user)


@app.route('/goals', methods=['POST', 'GET'])
@login_required
def goals():
    current_user.savings += update_savings()
    db.session.commit()
    all_goals = db.session.execute(db.Select(Goals).where(Goals.user_id == current_user.id)).scalars()
    if request.method == 'POST':
        try:
            goal_to_finish = db.session.execute(db.Select(Goals).where(Goals.id == request.form['done'])).scalar()
            current_user.savings = current_user.savings - goal_to_finish.amount
            db.session.delete(goal_to_finish)
            # remove and deduct money
        except:
            # just remove
            goal_to_remove = db.session.execute(db.Select(Goals).where(Goals.id == request.form['delete'])).scalar()
            db.session.delete(goal_to_remove)
        db.session.commit()

    return render_template('goals.html', user=current_user, goals=all_goals)


@app.route('/goals/add', methods=['POST', 'GET'])
@login_required
def add_goal():
    if request.method == 'POST':
        new_goal = Goals(
            name=request.form['name'],
            amount=request.form['amount'],
            user=current_user,
        )
        db.session.add(new_goal)
        db.session.commit()
    return redirect(url_for('goals'))


@app.route('/analytics')
@login_required
def analytics():
    # Graph Content
    # Expense Amounts by Category
    categories = db.session.query(Expense, func.sum(Expense.amount).label('total_amount')).filter(Expense.user_id == current_user.get_id()).group_by(Expense.category).order_by(desc('total_amount'))
    current_date = datetime.date.today()
    month = current_date.month
    year = current_date.year
    categories_monthly = db.session.query(Expense, func.sum(Expense.amount).label('total_amount')).filter(Expense.user_id == current_user.get_id(), func.extract('month', Expense.date) == month).group_by(Expense.category).order_by(desc('total_amount'))
    category_list = []
    amt_list = []
    for category in categories:
        category_list.append(category[0].category)
        amt_list.append(category[1])

    plt.clf()
    colors = ['lightcoral', 'cyan', 'palegreen', 'darkorange', 'mediumslateblue', 'pink', 'yellow']
    plt.pie(amt_list, colors=colors, startangle=90)
    plt.legend(category_list, loc="lower left")
    plt.axis('equal')
    plt.title('Total Expense by Category')
    plt.tight_layout()
    plt.savefig('static/images/category.png')

    category_list = []
    amt_list = []
    for category in categories_monthly:
        category_list.append(category[0].category)
        amt_list.append(category[1])
    plt.clf()
    plt.pie(amt_list, colors=colors, startangle=90)
    plt.legend(category_list, loc="lower left")
    plt.axis('equal')
    plt.title('Monthly Expense by Category')
    plt.tight_layout()
    plt.savefig('static/images/monthly_category.png')

    # Expenses by Month
    month_list = []
    expense_list = []
    expense_monthly = db.session.query(Expense, func.sum(Expense.amount).label('total_amount')).filter(Expense.user_id == current_user.get_id(), func.extract('month', Expense.date == month), func.extract('year', Expense.date) == year).group_by(func.extract('month', Expense.date)).order_by(func.extract('month', Expense.date))
    for monthly in expense_monthly:
        expense_list.append(monthly[1])
        month = datetime.datetime.strptime(monthly[0].date, "%Y-%m-%d")
        month_list.append(month.strftime("%b"))

    plt.clf()
    expense_list = np.array(expense_list)
    plt.bar(month_list, expense_list, color=colors)
    plt.title('Expenses by Month')
    plt.tight_layout()
    plt.savefig('static/images/monthly.png')

    # Expenses by Year
    expense_yearly = db.session.query(Expense, func.sum(Expense.amount).label('total_amount')).filter(Expense.user_id == current_user.get_id()).group_by(func.extract('year', Expense.date)).order_by(asc(func.extract('month', Expense.date)))
    year_list = []
    yearly_expense_list = []
    for yearly in expense_yearly:
        yearly_expense_list.append(yearly[1])
        year = datetime.datetime.strptime(yearly[0].date, "%Y-%m-%d")
        year_list.append(year.strftime("%Y"))

    plt.clf()
    plt.bar(year_list, yearly_expense_list, color=colors)
    plt.title('Expenses by Year')
    plt.tight_layout()
    plt.savefig('static/images/yearly.png')

    # Table Content
    expenses = db.session.execute(db.select(Expense).where(Expense.user_id == current_user.get_id())).scalars()
    cur_month = update_monthly(0, True)
    last_month = update_monthly(1, True)
    every_month_expense = []
    for i in range(1, 12):
        month_expense = update_monthly(i, False)
        if month_expense > 0:
            every_month_expense.append(month_expense)
    avg_expense = current_user.total_expense/len(expenses.all())
    monthly_avg_expense = sum(every_month_expense)/len(every_month_expense)
    smallest_category = db.session.query(Expense, func.sum(Expense.amount).label('total_amount')).filter(Expense.user_id == current_user.get_id()).group_by(Expense.category).order_by(asc('total_amount')).first()
    biggest_category = db.session.query(Expense, func.sum(Expense.amount).label('total_amount')).filter(Expense.user_id == current_user.get_id()).group_by(Expense.category).order_by(desc('total_amount')).first()
    smallest_expense = db.session.query(Expense, func.min(Expense.amount).label('total_amount')).filter(Expense.user_id == current_user.get_id()).first()[0]
    biggest_expense = db.session.query(Expense, func.max(Expense.amount).label('total_amount')).filter(Expense.user_id == current_user.get_id()).first()[0]

    return render_template('analytics.html', user=current_user, last_month=last_month, cur_month=cur_month, avg_expense=avg_expense, monthly_avg_expense=monthly_avg_expense, biggest_category=biggest_category, smallest_category=smallest_category, biggest_expense=biggest_expense, smallest_expense=smallest_expense)


@app.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dash():
    expenses = db.session.execute(db.select(Expense).where(Expense.user_id == current_user.get_id()).order_by(Expense.date.desc())).scalars()
    current_user.monthly_expense = update_monthly(0, True)
    amt_list = []
    date_list = []
    expense_list = []
    desc = ''
    if request.method == 'POST':
        str_range_date = []
        if request.form['start'] and request.form['end']:
            # Create Range of dates with starting and ending date
            # Converting to datetime obj to get dates in between
            start_date = datetime.datetime.strptime(request.form['start'], '%Y-%m-%d')
            end_date = datetime.datetime.strptime(request.form['end'], '%Y-%m-%d')
            range_date = []
            delta = end_date - start_date
            for i in range(delta.days + 1):
                day = start_date + datetime.timedelta(days=i)
                range_date.append(day)
            str_range_date = [date_obj.strftime('%Y-%m-%d') for date_obj in range_date]

        # Get all the dates if user didn't specify any
        if not str_range_date:
            for expense in expenses:
                str_range_date.append(expense.date)

        expenses = db.session.execute(db.select(Expense).where(Expense.user_id == current_user.get_id()).filter(Expense.date.in_(str_range_date)).order_by(Expense.date.desc())).scalars()
        desc = request.form['desc']
        category = request.form['category']
        if category:
            if request.form['sort'] == 'asc':
                expenses = db.session.execute(db.select(Expense).where(Expense.user_id == current_user.get_id(), Expense.category == category).filter(Expense.date.in_(str_range_date)).order_by(Expense.date.desc()).order_by(Expense.amount.asc())).scalars()
            else:
                expenses = db.session.execute(db.select(Expense).where(Expense.user_id == current_user.get_id(), Expense.category == category).filter(Expense.date.in_(str_range_date)).order_by(Expense.date.desc()).order_by(Expense.amount.desc())).scalars()
        if request.form['sort'] == 'asc' and not category:
            expenses = db.session.execute(db.select(Expense).where(Expense.user_id == current_user.get_id()).order_by(Expense.date.desc()).filter(Expense.date.in_(str_range_date)).order_by(Expense.amount.asc())).scalars()
        elif request.form['sort'] == 'desc' and not category:
            expenses = db.session.execute(db.select(Expense).where(Expense.user_id == current_user.get_id()).order_by(Expense.date.desc()).filter(Expense.date.in_(str_range_date)).order_by(Expense.amount.desc())).scalars()

    # Converting to lists to plot it into graph
    for expense in expenses:
        # If user gives description, exclude all expenses that don't match the given description
        if desc:
            if desc.lower() == expense.description.lower():
                amt_list.append(expense.amount)
                date_list.append(expense.date)
                expense_list.append(expense)
        else:
            amt_list.append(expense.amount)
            date_list.append(expense.date)
            expense_list.append(expense)

    plt.clf()
    converted_dates = list(map(datetime.datetime.strptime, date_list, len(date_list) * ['%Y-%m-%d']))
    x_axis = converted_dates
    formatter = dates.DateFormatter('%Y-%m-%d')
    plt.plot(x_axis, amt_list, 'r')
    ax = plt.gcf().axes[0]
    ax.xaxis.set_major_formatter(formatter)

    plt.xlabel("Date")
    plt.ylabel("Amount Spent")
    plt.plot_date(converted_dates, amt_list, 'k.')
    for i in range(0, len(expense_list)):
        plt.annotate(expense_list[i].description, (x_axis[i], amt_list[i]), xytext=(-17, 5), textcoords='offset pixels', fontsize=6)
    plt.gcf().autofmt_xdate(rotation=25)
    plt.savefig('static/images/graph.png')

    return render_template('dashboard.html', user=current_user, expenses=expense_list, bar=70)


@app.route('/delete_expense', methods=['POST', 'GET'])
@login_required
def delete_expense():
    if request.method == 'POST':
        exp_delete = db.session.execute(db.Select(Expense).where(Expense.id == request.form['delete'])).scalar()
        db.session.delete(exp_delete)
        db.session.commit()
    return redirect(url_for('dash'))


@app.route('/login', methods=['POST', 'GET'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = db.session.execute(db.select(User).where(User.email == email)).scalar()
        if user:
            if user.password == password:
                login_user(user)
                return redirect(url_for('home'))
            else:
                flash("Invalid Password", "error")
        else:
            flash("Invalid Email", "error")
    return render_template('login.html')


@app.route('/signup', methods=['POST', 'GET'])
def signup():
    if request.method == 'POST':
        result = db.session.execute(db.select(User).where(User.email == request.form['email'])).scalar()
        if not result:
            new_user = User(
                username=request.form['username'],
                email=request.form['email'],
                password=request.form['password'],
            )
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)
            return render_template('index.html')
        else:
            flash("Email already registered, Please Login", "error")
            return redirect(url_for('login'))
    return render_template('signup.html')


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('home'))


if __name__ == '__main__':
    app.run()

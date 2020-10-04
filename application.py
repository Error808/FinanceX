import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions
from werkzeug.security import check_password_hash, generate_password_hash
from passlib.apps import custom_app_context as pwd_context

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached


@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)


app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    # Query history of stocks shares
    info = db.execute(
        "SELECT stock, SUM(shares) AS shares, SUM(total) AS total FROM history WHERE id = :id GROUP BY stock", id=session["user_id"])

    # user's current cash
    cash = db.execute("SELECT cash FROM users WHERE id = :id",
                      id=session["user_id"])[0]['cash']

    total = cash
    # if it user bought anything
    if info:
        # grand total (cash plus stocks)
        for x in info:
            if x is not None and x['shares'] > 0:
                total = x['total'] + total

        # add current price in dollar sign to info
        j = 0
        for x in info:
            if x is not None:
                x['current'] = usd(lookup(x['stock'])["price"])
                x['currentT'] = usd(lookup(x['stock'])["price"] * info[j]['shares'])
                j = j+1

        return render_template("index.html", info=info, cash=usd(cash), total=usd(total))

    else:
        return render_template("index.html", cash=usd(cash), total=usd(total))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure symbol was inserted
        if not request.form.get("symbol"):
            return apology("must provide stock's symbol")

        if not request.form.get("shares") or not request.form.get("shares").isdigit() or int(request.form.get("shares")) <= 0:
            return apology("must provide positive number of shares", 400)

        # find infos about the quote
        quote = lookup(request.form.get("symbol"))

        if quote == None:
            return apology("invalid symbol of the stock")

        # user has to pay this much
        total = quote["price"] * int(request.form.get("shares"))

        # cash from user
        cash = db.execute("SELECT cash FROM users WHERE id = :id", id=session["user_id"])

        # check
        if total > cash[0]["cash"]:
            return apology("Can't afford")

        # add to history
        db.execute("INSERT INTO history (id, stock, price, shares, total) VALUES (:id, :stock, :price, :shares, :total)",
                   id=session["user_id"], stock=request.form.get("symbol"), price=float(quote["price"]), shares=int(request.form.get("shares")), total=total)

        # update user's cash
        db.execute("UPDATE users SET cash = cash - :total WHERE id = :id", total=total, id=session["user_id"])

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    info = db.execute("SELECT stock, price, shares, time FROM history WHERE id = :id", id=session["user_id"])
    # out the infos
    return render_template("history.html", info=info)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 400)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure symbol was inserted
        if not request.form.get("symbol"):
            return apology("must provide symbol of the stock", 400)

        # find infos about the quote
        quote = lookup(request.form.get("symbol"))

        if quote == None:
            return apology("invalid symbol of the stock", 400)

        quote['price'] = usd(quote['price'])

        # out the infos
        return render_template("quoted.html", info=quote)

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    if request.method == "POST":

        # Ensure username was entered
        if not request.form.get("username"):
            return apology("must provide username")

        # Ensure password was entered
        elif not request.form.get("password"):
            return apology("must provide password")

        # Ensure second password was entered
        elif not request.form.get("confirmation"):
            return apology("please re enter your password")

        # check if the passwords match
        if not request.form.get("password") == request.form.get("confirmation"):
            return apology("passwords don't match")

        # hash the password
        hash = generate_password_hash(request.form.get("password"))

        # insert username into database and also check if it's dublicated username
        result = db.execute("INSERT INTO users (username, hash) Values(:username, :hash)",
                            username=request.form.get("username"), hash=hash)

        if not result:
            return apology("This username already exists", 400)

        # log them in
        session["user_id"] = result

        # redirect to homepage
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure symbol was inserted
        if not request.form.get("symbol"):
            return apology("must provide stock's symbol")

        # check for shares field
        if not request.form.get("shares") or not request.form.get("shares").isdigit() or int(request.form.get("shares")) <= 0:
            return apology("must provide positive number of shares")

        # find infos about the quote if valid
        quote = lookup(request.form.get("symbol"))
        if quote == None:
            return apology("invalid symbol of the stock")

        hist = db.execute("SELECT stock, SUM(shares) AS shares FROM history WHERE id =:id and stock =:name",
                          id=session["user_id"], name=request.form.get("symbol"))

        # check if the user has the stock and valid shares
        if hist[0]['stock'] == None or int(request.form.get("shares")) > hist[0]['shares']:
            return apology("not a valid stock or a valid number of shares")

        # get cash from the users
        user = db.execute("SELECT cash FROM users WHERE id=:id", id=session["user_id"])

        # total price of the sale
        total = quote['price'] * int(request.form.get("shares"))

        # update users cash
        db.execute("UPDATE users SET cash = cash + :total WHERE id =:id", id=session["user_id"], total=total)

        db.execute("INSERT INTO history (id, stock, price, shares, total) VALUES (:id, :stock, :price, :shares, :total)",
                   id=session["user_id"], stock=request.form.get("symbol"), price=-1*quote["price"], shares=-1*int(request.form.get("shares")), total=-1*total)

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        info = db.execute("SELECT stock FROM history WHERE id = :id GROUP BY stock", id=session["user_id"])
        return render_template("sell.html", info=info)

# @app.route("/check", methods="GET")
# def check():
#     return True


def errorhandler(e):
    """Handle error"""
    return apology(e.name, e.code)


# listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)

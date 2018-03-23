from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from passlib.apps import custom_app_context as pwd_context
from tempfile import mkdtemp

from helpers import *

# configure application
app = Flask(__name__)

# ensure responses aren't cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response

# custom filter
app.jinja_env.filters["usd"] = usd

# configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

@app.route("/")
@login_required
def index():

    display = db.execute("SELECT * FROM Portfolio WHERE id=:id",id=session["user_id"])

    return render_template("index.html",stocks=display)

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock."""
    if request.method=="GET":
        return render_template("buy.html")

    else:

        result=lookup(request.form.get("symbol"))

        if not result:
            return apology("enter a correct symbol")

        numberofshares=int(request.form.get("price"))

        if numberofshares<0:
            return apology("enter a positive number")


        cash = db.execute("SELECT cash FROM users WHERE id=:id",id=session["user_id"])

        purchase = (result["price"]) * float(numberofshares)

        if float(cash[0]["cash"])<purchase:
            return apology("not enough cash to buy stocks")


        db.execute("INSERT INTO history (symbol, share, price, id) VALUES(:symbol, :share, :price, :id)",symbol=result["symbol"], share=numberofshares,price=usd(result["price"]), id=session["user_id"])



        db.execute("UPDATE users SET cash=cash-:purchase WHERE id =:id",id=session["user_id"],purchase=purchase)

        check = db.execute("SELECT shares FROM Portfolio WHERE id =:id AND symbol=:symbol",id=session["user_id"],symbol=result["symbol"])


        if not check:

            db.execute("INSERT INTO Portfolio(symbol,name,shares,price,total,id) Values(:symbol,:name,:shares,:price,:total,:id)",symbol=result["symbol"],name=result["name"],shares=numberofshares,price=result["price"],total=purchase,id=session["user_id"])

        else:

            sharecount=numberofshares+check[0]["shares"]

            total=(sharecount)*result["price"]

            db.execute("UPDATE Portfolio SET shares=:shares,total=:total WHERE id=:id AND symbol=:symbol",shares=sharecount,total=total,id=session["user_id"],symbol=result["symbol"])


        return redirect(url_for("index"))





@app.route("/history")
@login_required
def history():
    """Show history of transactions."""


    display = db.execute("SELECT * FROM history WHERE id=:id",id=session["user_id"])

    return render_template("history.html",histories=display)

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in."""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

        # ensure username exists and password is correct
        if len(rows) != 1 or not pwd_context.verify(request.form.get("password"), rows[0]["hash"]):
            return apology("invalid username and/or password")

        # remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # redirect user to home page
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/logout")
def logout():
    """Log user out."""

    # forget any user_id
    session.clear()

    # redirect user to login form
    return redirect(url_for("login"))

@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    if request.method == "GET":
        return render_template("quote.html")

    else:

        result=lookup(request.form.get("quote"))

        if not result:
            return apology("enter a correct symbol")

        return render_template("quoted.html",stock=result)




@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")
        elif request.form.get("passwordmatch")!=request.form.get("password"):
             return apology("password did not match")

        insert = db.execute("INSERT INTO users(username,hash) \
                           VALUES(:username,:hash)",\
                           username=request.form.get("username"),hash = pwd_context.encrypt(request.form.get("password")))

        if not insert:
            return apology("username already exist")

        # remember which user has logged in
        session["user_id"] = insert

        # redirect user to home page
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock."""
    return apology("TODO")

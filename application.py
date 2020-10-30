from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from passlib.apps import custom_app_context as pwd_context
from tempfile import gettempdir

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
app.config["SESSION_FILE_DIR"] = gettempdir()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

@app.route("/")
@login_required
def index():

    stocks = db.execute("SELECT * FROM stocks WHERE user_id = :user_id ORDER BY symbol ASC", user_id=session["user_id"])
    user = db.execute("SELECT * FROM users WHERE id = :id", id=session["user_id"])
    grand_total = 0.0
    
    for i in range(len(stocks)):
        stock = lookup(stocks[i]["symbol"])
        stocks[i]["company"] = stock["name"]
        stocks[i]["cur_price"] = "%.2f"%(stock["price"])
        stocks[i]["cur_total"] = "%.2f"%(float(stock["price"]) * float(stocks[i]["quantity"]))
        stocks[i]["profit"] = "%.2f"%(float(stocks[i]["cur_total"]) - float(stocks[i]["total"]))
        grand_total += stocks[i]["total"]
        stocks[i]["total"] = "%.2f"%(stocks[i]["total"])
    
    grand_total += float(user[0]["cash"])
     
    return render_template("index.html", stocks=stocks, cash=usd(user[0]["cash"]), grand_total=usd(grand_total))

@app.route("/account", methods=["GET", "POST"])
@login_required
def account():
    """Change account settings."""
    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        
        # ensure all fields are completed
        if not request.form.get("old_password") or not request.form.get("password") or not request.form.get("confirm_password"):
            return render_template("account.html")
        
        # assign to variable for easy handling
        old_password = request.form.get("old_password")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")
            
        # retrieve user data
        user = db.execute("SELECT * FROM users WHERE id = :user_id", user_id=session["user_id"])
        
        # ensure old password is correct and no errors
        if len(user) != 1 or not pwd_context.verify((old_password), user[0]["hash"]):
            return apology("password is incorrect")
            
        # ensure new passwords match
        if password != confirm_password:
            return apology("new passwords do not match")
            
        # commit new password to db
        hash = pwd_context.encrypt(password)
        db.execute("UPDATE users SET hash = :hash WHERE id = :user_id", hash=hash, user_id=session["user_id"])
        
        return render_template("account.html", success=1)
        
    # else if user reached route via GET (as by clicking a link or via redirect)  
    else:
        return render_template("account.html")

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock."""
    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        
        # ensure a symbol and quantity were submited
        if not request.form.get("symbol") or not request.form.get("quantity") or int(request.form.get("quantity")) < 1:
            return render_template("buy.html")
        
        symbol = request.form.get("symbol").upper()
        quantity = request.form.get("quantity")
        user_id = session["user_id"]
        
        # lookup the stock
        stock = lookup(symbol)

        # ensure symbol exists
        if not stock:
            return apology("symbol not found")

        # calculate total price
        total_price = float(stock["price"]) * float(quantity)
        
        user = db.execute("SELECT * FROM users WHERE id = :id", id=user_id)
        funds = float(user[0]["cash"])
        
        # check if user has enough funds
        if funds < total_price:
            return apology(top="not enough funds", bottom="available: " + str("%.2f"%funds))
        
        funds_left = funds - total_price
        
        # check if symbol is already owned
        stock_db = db.execute("SELECT * FROM stocks WHERE user_id = :user_id AND symbol = :symbol",
                            user_id=user_id, symbol=symbol)
        
        # update with new price if already owned   
        if len(stock_db) == 1:
            
            new_quantity = int(stock_db[0]["quantity"]) + int(quantity)
            new_total = float(stock_db[0]["total"]) + total_price
            new_pps = "%.2f"%(new_total / float(new_quantity))
            
            db.execute("UPDATE stocks SET quantity = :quantity, total = :total, pps = :pps WHERE user_id = :user_id AND symbol = :symbol",
                        quantity=new_quantity, total=new_total, pps=new_pps, user_id=user_id, symbol=symbol)
            
        # else create a new entry in db
        else:
            
            db.execute("INSERT INTO stocks (user_id, symbol, quantity, total, pps) VALUES (:user_id, :symbol, :quantity, :total, :pps)",
                        user_id=user_id, symbol=symbol, quantity=quantity, total=total_price, pps=stock["price"])
                        
        # modify available funds
        db.execute("UPDATE users SET cash = :cash WHERE id = :id", cash=funds_left, id=user_id)
        
        # commit to history
        db.execute("INSERT INTO history (user_id, action, symbol, quantity, pps) VALUES (:user_id, :action, :symbol, :quantity, :pps)",
                    user_id=user_id, action=1, symbol=symbol, quantity=quantity, pps=stock["price"])
        
        # send a success message
        return render_template("success.html", action="bought", quantity=quantity,
                                name=stock["name"], total=usd(total_price), funds=usd(funds_left))
        
    # else if user reached route via GET (as by clicking a link or via redirect)  
    else:
        return render_template("buy.html")

@app.route("/history")
@login_required
def history():
    """Show history of transactions."""
    
    # retrieve history from db
    stocks = db.execute("SELECT * FROM history WHERE user_id = :user_id ORDER BY date DESC", user_id=session["user_id"])
    
    # calculate total price of transaction
    for i in range(len(stocks)):
        stocks[i]["total"] = "%.2f"%(float(stocks[i]["quantity"]) * float(stocks[i]["pps"]))
        
    # render table
    return render_template("history.html", stocks=stocks)

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
    
    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        
        # ensure a symbol was submited
        if not request.form.get("symbol"):
            return render_template("quote.html")
        
        # request stock information    
        stock = lookup(request.form.get("symbol"))
        
        if not stock:
            return apology("symbol not found")

        return render_template("quoted.html", symbol=stock["symbol"], name=stock["name"], price=stock["price"])
    
    # else if user reached route via GET (as by clicking a link or via redirect)  
    else:
        return render_template("quote.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user."""
    
    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        
        # ensure username was submited
        if not request.form.get("username"):
            return apology("must provide username")
            
        # ensure email was submited
        elif not request.form.get("email"):
            return apology("must provide email")
            
        # ensure password was submited
        elif not request.form.get("password") or not request.form.get("confirm_password"):
            return apology("must provide password and confirmation")
            
        # ensure passwords match
        elif request.form.get("password") != request.form.get("confirm_password"):
            return apology("passwords do not match")
        
        # ensure username is unique
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))
        if len(rows) >= 1:
            return apology("username already exists")
            
        # ensure email is unique
        rows = db.execute("SELECT * FROM users WHERE email = :email", email=request.form.get("email"))
        if len(rows) >= 1:
            return apology("email already exists")
        
        # add user to database
        db.execute("INSERT INTO users (username, hash, email) VALUES (:username, :hash, :email)",
                    username=request.form.get("username"),
                    hash=pwd_context.encrypt(request.form.get("password")),
                    email=request.form.get("email"))
        
        # login user automatically and remember session
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))
        session["user_id"] = rows[0]["id"]
        
        # redirect to home page
        return redirect(url_for("index"))
        
    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock."""
    stocks = db.execute("SELECT * FROM stocks WHERE user_id = :user_id", user_id=session["user_id"])
    
    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        
        # ensure quantity was submited
        if not request.form.get("quantity") or int(request.form.get("quantity")) < 1:
            return render_template("sell.html", stocks=stocks)
        
        user_id = session["user_id"]
        symbol = request.form.get("symbol").upper()
        quantity = request.form.get("quantity")
        
        # retrieve stock from db
        stock_db = db.execute("SELECT * FROM stocks WHERE user_id = :user_id AND symbol = :symbol",
                            user_id=user_id, symbol=symbol)
        if stock_db:
            stock_db = stock_db[0]
        else:
            return render_template("sell.html", stocks=stocks)
                            
        # retrieve user data from db
        user = db.execute("SELECT * FROM users WHERE id = :id", id=user_id)
        
        # ensure quantity to be sold is available
        if int(quantity) > stock_db["quantity"]:
            return apology(top="not enough shares", bottom="available: " + str(stock_db["quantity"]))
        
        # lookup the stock to get current price
        stock = lookup(symbol)
        
        # calculate total price
        total_price = float(stock["price"]) * float(quantity)
        
        # modify number of shares owned or delete if < 1
        if int(quantity) == stock_db["quantity"]:
            db.execute("DELETE FROM stocks WHERE user_id = :user_id AND symbol = :symbol", user_id=user_id, symbol=symbol)
        else:
            new_quantity = int(stock_db["quantity"]) - int(quantity)
            new_total = float(new_quantity) * float(stock_db["pps"])
            db.execute("UPDATE stocks SET quantity = :quantity, total = :total WHERE user_id = :user_id AND symbol = :symbol",
                        quantity=new_quantity, total=new_total, user_id=user_id, symbol=symbol)

        # modify available funds
        funds_available = float(user[0]["cash"]) + total_price
        db.execute("UPDATE users SET cash = :cash WHERE id = :id", cash=funds_available, id=user_id)
        
        # commit to history
        db.execute("INSERT INTO history (user_id, action, symbol, quantity, pps) VALUES (:user_id, :action, :symbol, :quantity, :pps)",
                    user_id=user_id, action=0, symbol=symbol, quantity=quantity, pps=stock["price"])
        
        # send a success message
        return render_template("success.html", action="sold", quantity=quantity,
                                name=stock["name"], total=usd(total_price), funds=usd(funds_available))
        
    # else if user reached route via GET (as by clicking a link or via redirect)  
    else:
        return render_template("sell.html", stocks=stocks)

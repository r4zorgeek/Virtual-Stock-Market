from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from passlib.apps import custom_app_context as pwd_context
from tempfile import mkdtemp
from datetime import datetime
import sys

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

    # ensure user reached via route GET
    if request.method == "GET":

        # current user
        cur_user = session["user_id"]

        # user total cash
        # rows = db.execute("SELECT cash FROM users WHERE id=:user_id", user_id=session["user_id"])

        # user portfolio
        user_pf = db.execute("SELECT stockname, nstocks, cash FROM users JOIN purchase ON users.id = purchase.user_id WHERE user_id=:userid", userid=session["user_id"])
        if not user_pf:
            cash = db.execute("SELECT cash FROM users where id=:id", id=session["user_id"])
            cash = float("{0:2f}".format(cash[0]['cash']))
            return render_template("index.html", tcash=cash, gcash=cash)

        # total cash
        tcash = float("{0:.2f}".format(user_pf[0]["cash"]))
        gcash = 0.0

        # storing the data to be sended to the page
        send = list()

        for name in user_pf:
            data = lookup(name["stockname"])
            send.append({'symbol': data["symbol"], 'name': data["name"], 'shares': name["nstocks"], 'price': data["price"], 'total': name["nstocks"] * data["price"]})
            gcash = gcash + float((name["nstocks"] * data["price"]))

        gcash = tcash + gcash
        gcash = float("{0:.2f}".format(gcash))
        return render_template("index.html", pfolio=send, tcash=tcash, gcash=gcash)

    return apology("TODO")

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock."""

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure SYMBOL and Share is submitted
        if request.form.get("symbol") == "" or request.form.get("share") == "":
            return apology("Please Enter SYMBOL/SHARE CORRECTLY!")

        # ensure if stock exists
        elif lookup(request.form.get("symbol")) == None:
            return apology("SYMBOL DOES NOT EXIST!")

        # ensure if user input for share is positive
        elif int(request.form.get("share")) < 0:
            return apology("Cannot Buy Negative Shares Bruu!")

        # if everything is ok then ..
        # retrieve stock
        stock = lookup(request.form.get("symbol"))

        # stock price
        stock_price = stock["price"]

        # user cash
        user_cash = db.execute("SELECT cash FROM users WHERE id=:id", id = session["user_id"])
        user_cash = float(user_cash[0]["cash"])
        # ensure appropriate cash is available for purchase
        nShare = 0
        for i in request.form.get("share"):
            nShare = nShare + float(i)
        if not user_cash - stock_price * nShare >= 0:
            return apology("YOU DO NOT HAVE ENOUGH CASH")

        else:

           # check if stock already exists in purchase table, if yes then update the no. of stocks
           rows = db.execute("SELECT stockname FROM purchase WHERE user_id=:user_id AND stockname=:stockname", user_id=session["user_id"], stockname=request.form.get("symbol"))
           if rows:
               db.execute("UPDATE purchase SET nstocks = nstocks + :nstocks WHERE stockname = :stockname", nstocks=nShare, stockname=stock["symbol"])

           else:
               result = db.execute("INSERT INTO purchase (user_id, stockname, nstocks, price) VALUES (:user_id, :stockname, :nstocks, :price)",
                    user_id=session["user_id"], stockname=stock["symbol"], nstocks=nShare, price=stock_price)

           # bought
           by = "BUY"

           # current time
           c_time = str(datetime.utcnow())

           # insert data in history table
           db.execute("INSERT INTO history (user_id, stockname, nstocks, price, time, ty_purchase) VALUES (:user_id, :stockname, :nstocks, :price, :time, :b)", user_id=session["user_id"], stockname=stock["symbol"], nstocks=nShare, price=stock_price, time=c_time, b= by)

           # update the users cash
           db.execute("UPDATE users SET cash = cash - :tcash WHERE id=:user_id", tcash=stock_price*nShare,user_id=session["user_id"])

           return redirect(url_for("index"))
    # if user reached route via GET (as by submitting a form via GET)
    else:
        return render_template("buy.html")

    return apology("TODO")

@app.route("/history")
@login_required
def history():
    """Show history of transactions."""
    hist = db.execute("SELECT stockname, nstocks, price, time, ty_purchase FROM history WHERE user_id=:id", id=session["user_id"])
    if not hist:
        return apology("SORRY NO TRANSACTIONS TILL NOW")
    else:
        return render_template("history.html", transaction=hist)

    return apology("TODO")

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

    # if user reached route via GET (as by submitting a form via GET)
    if request.method == "GET":
        return render_template("quote.html")

    # if user reached route via POST (as by submitting a form via POST)
    elif request.method == "POST":
        return render_template("quoted.html", stockquote=lookup(request.form.get("symbol")))

    return apology("TODO")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user."""

    if request.method == "GET":
        return render_template("register.html")

    else:
        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # ensure same password is submitter again
        elif not request.form.get("password") == request.form.get("confirm-password"):
            return apology("must provide the same password for confirm password")

        # insert user in the table
        result = db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)", username=request.form.get("username"), hash=pwd_context.hash(request.form.get("password")))
        if not result:
            return apology("Username Already Exists")
        else:
            rows = db.execute("SELECT * FROM users where username = :username", username=request.form.get("username"))
            session["user_id"] = rows[0]["id"]

        return redirect(url_for("index"))

    return apology("TODO")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock."""

    # ensure if user reached route via GET.
    if request.method == "GET":

        # current user
        cur_user = session["user_id"]

        # user portfolio
        user_pf = db.execute("SELECT stockname, nstocks FROM purchase WHERE user_id=:userid", userid=session["user_id"])

        # storing the data to be sended to the page
        send = list()

        # storing sending data from table
        for data in user_pf:
            send.append(data["stockname"])

        return render_template("sell.html", pfolio=send)

    # if user reached via route POST
    else:

        # get stockname from user
        stockname = request.form.get("stockname")

        # get no. of shares
        shares = int(request.form.get("shares"))

        # user portfolio
        user_pf = db.execute("SELECT stockname, nstocks FROM purchase WHERE user_id=:userid AND stockname=:sname", userid=session["user_id"], sname=stockname)

        # ensure no. of shares is <= to total shares owned by user
        if not shares <= user_pf[0]["nstocks"]:
            return apology("Enter Shares Only How Much You Have!")

        #current price of stock
        cprice = lookup(stockname)["price"]

        # update no. of stocks for user
        result = db.execute("UPDATE purchase SET nstocks = nstocks - :share WHERE stockname = :sname AND user_id=:id", share=shares, sname=stockname, id=session["user_id"])
        if not result:
            return apology("Could Not Update Stocks")

        # update the cash of the user
        db.execute("UPDATE users SET cash = cash + :cash WHERE id=:id", cash=cprice*shares, id=session["user_id"])

        # current time
        c_time = str(datetime.utcnow())

        # sold
        sl = "SELL"

        # insert the transaction in the history
        db.execute("INSERT INTO history (user_id, stockname, nstocks, price, time, ty_purchase) VALUES (:user_id, :sname, :nstocks, :price, :time, :s)", user_id=session["user_id"], sname= stockname, nstocks=-shares, price=cprice, time=c_time, s=sl)

        user_pf = db.execute("SELECT nstocks FROM purchase WHERE user_id=:userid AND stockname=:sname", userid=session["user_id"], sname=stockname)
        # if shares of stock is 0 then remove stock from database
        if user_pf[0]["nstocks"] == 0:
            db.execute("DELETE FROM purchase WHERE stockname=:sname AND user_id=:id", sname=stockname, id=session["user_id"])

        return redirect(url_for("index"))

    return apology("TODO")


@app.route("/change_pass", methods=["GET", "POST"])
@login_required
def change_pass():
    """ Change Password of User. """

    # ensure if user reached via route GET.
    if request.method == "GET":
        return render_template("change_pass.html")

    # if user reached via route POST
    else:
        print(request.form, file=sys.stderr)
        # users current password
        cur_pass = request.form.get("cur_pass")

        # new password
        new_pass = request.form.get("new_pass")

        # confirm new password
        confirm_pass = request.form.get("confirm_pass")

        # get current user password
        cur_user_pass = db.execute("SELECT hash FROM users WHERE id=:id", id=session["user_id"])

        # check if current input password is equal to password stored in table
        if not pwd_context.verify(cur_pass, cur_user_pass[0]["hash"]):
            return apology("Please Enter Current Password Correctly")

        elif new_pass == "":
            return apology("Please Enter New Password")

        elif new_pass != confirm_pass:
            return apology("Please Eneter New Password and Confirm Password Same.")

        # update users password with new password
        result = db.execute("UPDATE users SET hash=:new_p WHERE id=:id", new_p=pwd_context.hash(new_pass), id=session["user_id"])
        if not result:
            return apology("ERROR")
        else:
            s = "Password Changed Successfully"
            return render_template("change_pass.html", str=s)

    return apology("NOTHING")

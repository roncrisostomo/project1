import os

from flask import Flask, render_template, request, session
from flask import redirect, url_for, abort, jsonify
from flask_debugtoolbar import DebugToolbarExtension
from functools import wraps
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
import requests

app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Set a secret key to enable Flask session cookies
app.config['SECRET_KEY'] = 'testeretset'

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
app.config["DEBUG_TB_INTERCEPT_REDIRECTS"] = False
app.url_map.strict_slashes = False
Session(app)

toolbar = DebugToolbarExtension(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None or session["user_id"] < 0:
            return redirect(url_for('index', next = request.url))
        return f(*args, **kwargs)
    return decorated_function

@app.route("/")
def index():
    # If no user_id session data yet, initialize to -1 (i.e. logged out)
    if session.get("user_id") is None:
        session["user_id"] = -1
    
    # If user is logged in, redirect to bookSearch page
    if session["user_id"] > -1:
        return redirect(url_for('bookSearch'))
    
    # Show login page
    return redirect(url_for('login'))

@app.route("/login", methods = ["GET", "POST"])
def login():
    if request.method == "GET":
        # Show log-in/register options
        return render_template("index.html")
    
    else: #if request.method == "POST":
        # Get name and password from forms
        name = request.form.get("name")
        password = request.form.get("password")
        
        if name == None or name == "":
            return render_template("error.html", message="Name field is blank.")
        
        # Look for user in database
        user = db.execute("SELECT * FROM users WHERE name = :name",
                          {"name": name}).fetchone()
        db.commit()
        # If name is not found in database or password is wrong, show error page
        if user is None:
            return render_template("error.html", message="We don't have a user named " + name)
        elif user.password != password:
            return render_template("error.html", message="Incorrect password")
        # If name-password combination exists in users database
        else:
            # Log in user
            session["user_id"] = user.user_id
            # Save user name for display in every page
            session["user_name"] = user.name
            # Load book search page
            return redirect(url_for('bookSearch'))

@app.route("/logout", methods = ["GET", "POST"])
@login_required
def logout():
    session["user_id"] = -1
    return redirect(url_for('index'))

@app.route("/register", methods = ["POST"])
def register():
    return render_template("register.html")

@app.route("/tryregister", methods = ["POST"])
def tryregister():
    # Get name, password, and retyped password from forms
    name = request.form.get("name")
    password = request.form.get("password")
    retypedPassword = request.form.get("retypedPassword")
    
    # Fields must not be empty
    if (name is None or password is None or retypedPassword == None or
        name.strip() == "" or password == "" or retypedPassword == ""):
        return render_template("error.html", message = "Please fill in all fields")
    
    # Password and retyped password must match
    if password != retypedPassword:
        return render_template("error.html", message = "Password and retyped password do not match")
    
    # Helper functions for validating input
    def countLetters(s):
        c = 0
        for char in s:
            if char.isalpha():
                c += 1
        return c
    def countNumbers(s):
        c = 0
        for char in s:
            if char.isnumeric():
                c += 1
        return c
    
    # Name must have at least 3 letters and/or numbers
    if countLetters(name) + countNumbers(name) < 3:
        return render_template("error.html", message = "Name must have at least 3 letters and/or numbers")
    
    # Password must have at least one letter and at least one number
    if countLetters(password) < 1 or countNumbers(password) < 1:
        return render_template("error.html", message = "Password must have at least one letter and at least one number")
    
    # Name must be available (i.e. no other user with same name)
    if db.execute("SELECT * FROM users WHERE name = :name", {"name": name}).rowcount > 0:
        return render_template("error.html", message = "That name is taken. Please choose another name.")
    
    # Remove leading and trailing spaces from name
    name = name.strip()
    
    # Add new user to database
    db.execute("INSERT INTO users (name, password) VALUES (:name, :password)",
               {"name": name, "password": password})
    db.commit()
    
    # Log in new user
    newUser = db.execute("SELECT * FROM users WHERE name = :name",
                         {"name": name}).fetchone()
    session["user_id"] = newUser.user_id
    # Save user name for display in every page
    session["user_name"] = newUser.name
    
    return render_template("registered.html")

@app.route("/success")
def success():
    if request.method == 'GET':
        return redirect(url_for('index'))
    
    return render_template("registered.html")

@app.route("/bookSearch", methods = ["GET", "POST"])
@login_required
def bookSearch():
    searchQuery = ""
    searchType = ""
    page = 1
    
    if request.method == 'GET':
        searchQuery = request.args.get("searchQuery", default = "", type = str)
        searchType = request.args.get("searchType", default = "", type = str)
        try:
            page = request.args.get("page", default = 1, type = int)
        except ValueError:
            return redirect(url_for('bookSearch',
                                    searchQuery = searchQuery,
                                    searchType = searchType))
        
    else: #if request.method == 'POST':
        searchQuery = request.form.get("searchQuery", default = "", type = str)
        searchType = request.form.get("searchType", default = "", type = str)
        try:
            page = request.form.get("page", default = 1, type = int)
        except ValueError:
            return redirect(url_for('bookSearch',
                                    searchQuery = searchQuery,
                                    searchType = searchType))
    
    # If search type is invalid, search for titles by default
    if searchType.lower() not in ["title", "author", "isbn"]:
        searchType = "title"
    
    # Get total number of pages of search result
    pageCount = 0
    showCount = 25
    # If no query, list showCount books from database
    if searchQuery == "":
        resultCount = db.execute("SELECT * FROM books").rowcount
    else:
        # Note: searchType is added to query as a direct string because :searchType
        #   inserts quotes (e.g. 'title'), which would break the WHERE clause
        # Safe to do because searchType is restricted to a set of values
        resultCount = db.execute("SELECT * FROM books WHERE LOWER(" + searchType
                                + ") LIKE :searchQuery",
                               {"searchQuery": '%' + searchQuery.lower() + '%'}).rowcount
    db.commit()
    pageCount = resultCount // showCount + 1
    
    # Limit page argument
    if pageCount > 0:
        if page < 1:
            return redirect(url_for('bookSearch',
                                    page = 1,
                                    searchQuery = searchQuery,
                                    searchType = searchType))
        if page > pageCount:
            return redirect(url_for('bookSearch',
                                    page = pageCount,
                                    searchQuery = searchQuery,
                                    searchType = searchType))
    
    offset = showCount * (page - 1)
    
    # If no query, list showCount books from database
    if searchQuery == "":
        # Load bookSearch page, showing the first 10 books in database by default
        books = db.execute("SELECT * FROM books LIMIT :showCount OFFSET :offset",
                           {"showCount": showCount, "offset": offset}).fetchall()
    else:
        books = db.execute("SELECT * FROM books WHERE LOWER(" + searchType
                            + ") LIKE :searchQuery LIMIT :showCount OFFSET :offset",
                           {"searchQuery": '%' + searchQuery.lower() + '%',
                            "showCount": showCount, "offset": offset}).fetchall()
    db.commit()
    
    return render_template("bookSearch.html",
                           userName = session["user_name"],
                           searchQuery = searchQuery,
                           searchType = searchType,
                           searchTypes = ["Title", "Author", "ISBN"],
                           queriedBooks = books,
                           curPage = page,
                           pageCount = pageCount)

@app.route("/bookSearch/<string:isbn>")
@login_required
def book(isbn):
    # Check if book with given isbn is in database
    book = db.execute("SELECT * FROM books WHERE isbn = :isbn",
                      {"isbn": isbn}).fetchone()
    # If not in database, return 404 error
    if book is None:
        abort(404)
    
    # Get average rating and number of ratings for the book from Goodreads,
    #   if available
    res = requests.get("https://www.goodreads.com/book/review_counts.json",
                       params = {"key": "RVO4B4rG7LVt41u4gYyw1g",
                                 "isbns": isbn})
    ratingsCount = -1
    averageRating = -1
    if res != None:
        try:
            ratingsCount = int(res.json()['books'][0]['ratings_count'])
            averageRating = float(res.json()['books'][0]['average_rating'])
        except ValueError:
            ratingsCount = -1
            averageRating = -1
    
    # Otherwise, load book page
    # Create dictionary of reviews for that book from other users in this website
    rawReviews = db.execute("SELECT * FROM reviews WHERE isbn = :isbn",
                            {"isbn": isbn}).fetchall()
    otherUserReviews = []
    # Separate current user's review data (if any)
    curUserReview = (0, "")
    for rawReview in rawReviews:
        # Map other user's name to tuple of rating and review
        # { [user name] : ([rating], [review]) }
        if rawReview.user_id != session["user_id"]:
            # Get user name from users table
            reviewer = db.execute("SELECT * FROM users WHERE user_id = :user_id",
                                  {"user_id": rawReview.user_id}).fetchone()
            otherUserReviews.append((reviewer.name, rawReview.rating, rawReview.review, ))
        # Pass in current user's review separately
        else:
            curUserReview = (rawReview.rating, rawReview.review)
    
    return render_template("book.html",
                           userName = session["user_name"],
                           book = book,
                           ratingsCount = ratingsCount,
                           averageRating = averageRating,
                           otherUserReviews = otherUserReviews,
                           curUserReview = curUserReview)

@app.route("/api/<string:isbn>", methods = ["GET"])
@login_required
def bookAPI(isbn):
    # Check if book with given isbn is in database
    book = db.execute("SELECT * FROM books WHERE isbn = :isbn",
                      {"isbn": isbn}).fetchone()
    # If not in database, return 404 error
    if book is None:
        abort(404)
        
    # If in database, return JSON response containing details from goodreads
    res = requests.get("https://www.goodreads.com/book/review_counts.json",
                       params = {"key": "RVO4B4rG7LVt41u4gYyw1g",
                                 "isbns": isbn})
    return jsonify(
        title = book.title,
        author = book.author,
        year = book.year,
        isbn = isbn,
        review_count = res.json()['books'][0]['reviews_count'],
        average_score = res.json()['books'][0]['average_rating'])

@app.route("/bookSearch/submitReview", methods = ["POST"])
@login_required
def submitReview():
    isbn = request.form.get("isbn", default = "", type = str)
    if isbn == "":
        return redirect(url_for("bookSearch"))
    
    # Make sure rating and review are valid
    try:
        rating = request.form.get("rating", default = 0, type = int)
    except ValueError:
        return render_template("error.html", message = "Invalid rating.")
    
    if rating < 0 or rating > 5:
        return render_template("error.html", message = "Invalid rating.")
    
    if rating == 0:
        return render_template("error.html", message = "Please select a rating.")
    
    review = request.form.get("review", default = "", type = str)
    if review.strip() == "":
        return render_template("error.html", message = "Please write a review.")
    
    # If current user has a previous review for book, update record
    if db.execute("SELECT * FROM reviews WHERE isbn = :isbn AND user_id = :user_id",
                  {"isbn": isbn, "user_id": session["user_id"]}).rowcount > 0:
        # Update rating
        db.execute("UPDATE reviews SET rating = :rating WHERE isbn = :isbn AND user_id = :user_id",
                   {"rating": rating, "isbn": isbn, "user_id": session["user_id"]})
        # Update review            
        db.execute("UPDATE reviews SET review = :review WHERE isbn = :isbn AND user_id = :user_id",
                   {"review": review, "isbn": isbn, "user_id": session["user_id"]})
    # Otherwise, create new review record
    else:
        db.execute("INSERT INTO reviews (isbn, user_id, rating, review) VALUES (:isbn, :user_id, :rating, :review)",
                   {"isbn": isbn, "user_id": session["user_id"], "rating": rating, "review": review})
    
    db.commit()
    
    return render_template("success.html", message = "Review submitted!")
    
    # TODO: Show success message in same page
#    return redirect(url_for('book', isbn = isbn, otherUserReviews = ..., curUserReview = ...))
    

from functools import wraps
import os
from urllib import request
import requests
import json
from flask import Flask, session, render_template, redirect, flash, request, g, url_for
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from werkzeug.security import check_password_hash, generate_password_hash
import psycopg2

app = Flask(__name__)

# Check for environment variable
# if not os.getenv("DATABASE_URL"):
#   raise RuntimeError("DATABASE_URL is not set")
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")


# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))

def login_required(f):
    """
    Decorate routes to require login.

    http://flask.pocoo.org/docs/0.12/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("users_pkey") is None:
            return redirect("/login")

        return f(*args, **kwargs)
    return decorated_function


@app.route("/")
@login_required
def index():
    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    session.clear()
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        user = db.execute(
            "SELECT * FROM users WHERE username = :username", {"username": username}).fetchall()
        if not username or not password:
            flash('Debe rellenar todos los campos')
            return redirect(url_for("login"))
        if len(user) == 0:
            Error = 'Invalid credentials'
            flash('Nombre de usuario o contraseña inválidos')
            return redirect(url_for("login"))
        if not check_password_hash(user[0]["password"], password):
            Error = 'Invalid credentials'
            flash(' contraseña inválidos')
            return redirect(url_for("login"))

        print(user[0]["id"])
        session["users_pkey"] = user[0]["id"]
        return redirect("/")
    else:
        return render_template("login.html")


@app.route("/isbn/<isbn>")
@login_required
def info(isbn):

    response = requests.get(
        "https://www.googleapis.com/books/v1/volumes?q=isbn:"+isbn+"&maxResults=1").json()
    datos = response

    libros = db.execute("SELECT id, isbn, title, author, year FROM books WHERE isbn = :isbn", {
                        "isbn": isbn}).fetchall()

    if len(libros) != 0:

        titulo = ""
        description = ""
        rating = ""
        cant_vot = ""
        imagen = ""

        try:
            titulo = datos["items"][0]["volumeInfo"]["title"]
        except:
            titulo = "No se encontró el título"

        try:
            description = datos["items"][0]["volumeInfo"]["description"]
        except:
            description = "No se encontró la descripción"

        try:
            rating = datos["items"][0]["volumeInfo"]["averageRating"]
        except:
            rating = "No se encontró la información"

        try:
            imagen = datos["items"][0]["volumeInfo"]["imageLinks"]["smallThumbnail"]
        except:
            imagen = "#"

        try:
            cant_vot = datos["items"][0]["volumeInfo"]["ratingsCount"]
        except:
            cant_vot = "No se encontró la información"

        bookid = libros[0]["id"]
        comentarios = db.execute("SELECT user_id, reviews.id, review, score, username FROM reviews INNER JOIN users ON user_id = users.id WHERE book_id = :book_id", {
                                 "book_id": bookid}).fetchall()
        c_u = db.execute("SELECT review, score FROM reviews WHERE book_id = :book_id AND user_id = :user_id", {
                         "book_id": bookid, "user_id": session["users_pkey"]}).fetchall()

        creador = False

        try:
            c_u[0]["review"]
            if len(c_u[0]["review"]) > 0:
                creador = True
        except:
            creador = False
        print(creador)

        return render_template("info.html", libros=libros, titulo=titulo, description=description, rating=rating, votes=cant_vot, imagen=imagen, creador = creador,comentarios = comentarios )
    else:
        print("no hay libros")
        return render_template("error.html"), 404


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        name = request.form.get("name")
        confirm = request.form.get("confirm")

        usernamedb = db.execute("SELECT username FROM users WHERE username = :username", {
                                "username": request.form.get("username")}).fetchall()

        if not username or not password or not name or not confirm:
            flash('Debe rellenar todos los campos')
            return render_template("login.html")

        if confirm != password:
            flash('Las contraseñas no coinciden')
            return render_template("register.html")

        if len(usernamedb) != 0:
            flash('El nombre de usuario ya está en uso')
            return render_template("register.html")

        if len(usernamedb) == 0 and password == confirm:
            datos = db.execute("INSERT INTO users (username, password, name) VALUES (:username,:password,:name) RETURNING id", {
                               "username": username, "password": generate_password_hash(password), "name": name}).fetchall()
            db.commit()

            print(datos)
            session["users_pkey"] = datos
        return redirect("/")
    else:
        return render_template("register.html")


@app.route("/search", methods=["POST"])
@login_required
def search():
    if request.method == "POST":
        busq = request.form.get("search")
        x = "%"+busq+"%"
        buscar = db.execute(
            "SELECT isbn, title, author, year FROM books WHERE LOWER(title) LIKE LOWER(:x) OR LOWER(author) LIKE LOWER(:x) OR LOWER(isbn) LIKE LOWER(:x)", {"x": x}).fetchall()
        if len(buscar) == 0:
            flash('Ningún libro, autor o ISBN coincide con la búsqueda')
        return render_template("libros.html", books=buscar, result=busq)


@app.route("/api/<isbn>")
def api(isbn):

    response = requests.get(
        "https://www.googleapis.com/books/v1/volumes?q=isbn:"+isbn+"&maxResults=1").json()
    datos = response
    try:
        libro = db.execute("SELECT id, isbn, title, author, year FROM books WHERE isbn = :isbn", {
                           "isbn": isbn}).fetchall()
        author = libro[0]["author"]
        title = libro[0]["title"]
        year = libro[0]["year"]
        rating = ""
        cant_vot = ""

        try:
            rating = datos["items"][0]["volumeInfo"]["averageRating"]
        except:
            rating = "No se encontró"

        try:
            cant_vot = datos["items"][0]["volumeInfo"]["ratingsCount"]
        except:
            cant_vot = "No se encontró"

        info = {"ISBN": isbn, "Title": title, "Author": author,
                "Year": year, "Rating": rating, "Ratings Count": cant_vot}

        print(author, rating)
        return info
    except:
        return "No se encontró el libro solicitado", 404

@app.route("/reviews",  methods=["GET","POST"])
@login_required
def reviews():
    if request.method == "POST":
        isbn = request.form.get("isbn")
        book_id = request.form.get("book_id")
        review = request.form.get("comentario")

        c_u = db.execute("SELECT review, score, id FROM reviews WHERE book_id = :book_id AND user_id = :user_id", {"book_id": book_id, "user_id": session["users_pkey"]}).fetchall()
        try:
            r_id = c_u[0]["id"]
        except:
            r_id = ""

        print(r_id)
        creador = False

        try:
            score = request.form.get("inlineRadioOptions")
            if score is None:
                flash("No puede dejar ningún campo vacío")
                return redirect("/isbn/" + isbn)
        except:
            flash("No puede dejar ningún campo vacío")
            return redirect("/isbn/" + isbn)

        if len(c_u) == 0:
            creador = False
            comentario = db.execute("INSERT INTO reviews (review, score, book_id, user_id) VALUES (:review, :score, :book_id, :user_id)", {"review": review, "score":score, "book_id": book_id, "user_id": session["users_pkey"]})
            db.commit()
        else:
            creador = True
            db.execute("UPDATE reviews SET score = :score, review= :review WHERE id= :id AND user_id = :user_id", {"score": score, "review": review, "id": r_id, "user_id": session["users_pkey"]})
            db.commit()
        print(creador)
        return redirect("/isbn/" + isbn)
    else:
        isbn = request.form.get("isbn")
        return redirect("/isbn/" + isbn)


@app.route("/logout")
def salir():
    session.clear()
    return redirect("/")


if __name__ == "__main__":
    app.run(debug=True, port=8000)

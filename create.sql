CREATE TABLE users (
    user_id SERIAL PRIMARY KEY,
    name VARCHAR NOT NULL,
    password VARCHAR NOT NULL
);

CREATE TABLE books (
    isbn VARCHAR PRIMARY KEY,
    title VARCHAR NOT NULL,
    author VARCHAR NOT NULL,
    year INTEGER NOT NULL
);

CREATE TABLE reviews (
    isbn VARCHAR REFERENCES books,
    user_id INTEGER REFERENCES users,
    rating INTEGER NOT NULL,
    review VARCHAR NOT NULL
);

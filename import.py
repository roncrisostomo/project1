import csv
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from itertools import islice

engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))

def main():
    # Read books data from csv
    with open("books.csv") as f:
        reader = csv.reader(f)
        # Skip the headers row
        next(reader, None)
        
        # Break up data upload into batches--5000 rows -> 5 batches of 1000
        batchCount = 5
        rowsPerBatch = 1000
        for batchNo in range(batchCount):
            # Insert each row of data into database
            for isbn, title, author, year in islice(reader, rowsPerBatch):
                db.execute("INSERT INTO books (isbn, title, author, year) VALUES (:isbn, :title, :author, :year)",
                         {"isbn": isbn, "title": title, "author": author, "year": year})
                print(f"Added book {isbn}, {title}, {author}, {year}.")
            # Commit current batch
            db.commit()

if __name__ == "__main__":
    main()

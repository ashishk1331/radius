import json
import sqlite3 as sql
from repository import QUERIES


def load_bookmarks():
    with open("bookmarks.json", "r", encoding="utf-8") as file:
        return json.load(file)


def Ingest():
    bookmarks = load_bookmarks()

    with open("migration.sql", "r") as file:
        migration = file.read()

    con = sql.connect("bookmarks.db")

    con.execute("PRAGMA foreign_keys = ON;")
    con.executescript(migration)

    with con:
        for each in bookmarks["data"]:
            # Firstly upsert the author
            author = each["author"]
            con.execute(
                QUERIES["UPSERT"]["AUTHOR"],
                (
                    author["id"],
                    author["screenName"],
                    author["name"],
                    author["profileImageUrl"],
                ),
            )

        for each in bookmarks["data"]:
            author = each["author"]

            # Upsert tweets
            con.execute(
                QUERIES["UPSERT"]["TWEET"],
                (each["id"], author["id"], each["text"], each["createdAt"], None, None),
            )

            # Add media for the tweet
            for media in each["media"]:
                con.execute(
                    QUERIES["UPSERT"]["MEDIA"],
                    (each["id"], media["url"], media["type"]),
                )

    con.close()

if __name__ == "__main__":
    Ingest()
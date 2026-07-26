import json
import sqlite3 as sql

QUERIES = {
    "UPSERT": {
        "TWEET": None,
        "AUTHOR": None,
        "MEDIA": None,
    },
    "SELECT": {
        "AUTHOR": None,
    },
}


def load_queries():
    with open("queries/upsert_author.sql", "r") as q:
        QUERIES["UPSERT"]["AUTHOR"] = q.read()
    with open("queries/upsert_tweet.sql", "r") as q:
        QUERIES["UPSERT"]["TWEET"] = q.read()
    with open("queries/upsert_media.sql", "r") as q:
        QUERIES["UPSERT"]["MEDIA"] = q.read()
    with open("queries/select_author.sql", "r") as q:
        QUERIES["SELECT"]["AUTHOR"] = q.read()


def load_bookmarks():
    with open("bookmarks.json", "r", encoding="utf-8") as file:
        return json.load(file)


def Ingest():
    bookmarks = load_bookmarks()
    load_queries()

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

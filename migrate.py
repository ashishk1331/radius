import sqlite3 as sql


def Migrate():
    con = sql.connect("bookmarks.db")
    con.execute("PRAGMA foreign_keys = ON;")

    with open("migration.sql", "r") as file:
        migration = file.read()
    
    con.executescript(migration)


if __name__ == "__main__":
    Migrate()

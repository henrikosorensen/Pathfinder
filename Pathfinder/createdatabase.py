import os
import sys
import requests
import subprocess
import tempfile
import sqlite3

pathfinderDataUrls = {
    "feats": "https://docs.google.com/spreadsheet/pub?key=0AhwDI9kFz9SddEJPRDVsYVczNVc2TlF6VDNBYTZqbkE&output=csv",
    "magicitems": "https://docs.google.com/spreadsheet/pub?key=0AhwDI9kFz9SddHI0N244NjJ0LVJrQzhvTXdWZmtWcVE&output=csv",
    "monsters": "https://docs.google.com/spreadsheet/pub?key=0AhwDI9kFz9SddHI0N244NjJ0LVJrQzhvTXdWZmtWcVE&output=csv",
    "npcs": "https://spreadsheets.google.com/pub?key=0AhwDI9kFz9SddFQ4SE40b0Q4MnZCazNuRnNkQTY4LWc&hl=en&output=csv",
    "spells": "https://spreadsheets.google.com/pub?key=0AhwDI9kFz9SddG5GNlY5bGNoS2VKVC11YXhMLTlDLUE&output=csv"
}

databaseFile = "pathfinder.sqlite"
connString = "sqlite:///{0}".format(databaseFile)


def queryRows(cursor, query):
    cursor.execute(query)
    return cursor.fetchall()


def renameSpell(name):
    left, sep, right = name.partition(',')

    return '{0} {1}'.format(right, left)


def httpDownload(url):
    r = requests.get(url)

    r.raise_for_status()

    encoding = r.encoding if r.encoding is not None else r.apparent_encoding

    return encoding, r.text


def importCSVtoTable(connectionString, tableName, csvFile):
    cmd = "csvsql --db {2} --insert --tables {0} {1}".format(tableName, csvFile, connectionString)
    subprocess.check_output(cmd.split(' '))


def renameSpells():
    conn = sqlite3.connect(databaseFile)

    rowsModified = -1
    try:
        cursor = conn.cursor()

        commaQuery = "select name from spells where instr(name, ',') > 0"

        spellsToBeRenamed = [(renameSpell(oldName[0]), oldName[0]) for oldName in queryRows(cursor, commaQuery)]

        query = 'update spells set name = ? where name = ?'
        cursor.executemany(query, spellsToBeRenamed)

        conn.commit()
        rowsModified = cursor.rowcount
        conn.close()
    except Exception as e:
        print(str(e))

        conn.rollback()
        conn.close()
        sys.exit(1)

    return rowsModified

def importData(connectionString, table, url):
    encoding, data = httpDownload(url)

    fileHandle, fileName = tempfile.mkstemp(".csv", text=True, dir=".")

    try:
        with os.fdopen(fileHandle, mode="w") as tmpFile:
            tmpFile.write(data)
            tmpFile.flush()

            importCSVtoTable(connectionString, table, fileName)
    except Exception as e:
        print(str(e))
        sys.exit(1)
    finally:
        os.unlink(fileName)


for table, url in pathfinderDataUrls.items():
    print("Importing {0}...".format(table))
    importData(connString, table, url)

print("{0} spells renamed.".format(renameSpells()))

print("Done!")
sys.exit(0)

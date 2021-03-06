import sqlite3

def dictFactory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d


class Database(object):
    def __init__(self, path):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = dictFactory

    def close(self):
        self.conn.close()
        self.conn = None

    def cursor(self):
        return self.conn.cursor()

    def selectOne(self, select, parameters):
        r = self.cursor().execute(select, parameters)

        if r.rowcount == 0:
            return {}
        else:
            return r.fetchone()

    def selectMany(self, select, parameters):
        r = self.cursor().execute(select, parameters)

        if r.rowcount == 0:
            return []
        else:
            return r.fetchall()

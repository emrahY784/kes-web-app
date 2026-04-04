import sqlite3
import pandas as pd

class DataFetcher:
    def __init__(self, db_path='kes_data_unified.db'):
        self.db_path = db_path

    def get_available_sources(self, table_name):
        conn = sqlite3.connect(self.db_path)
        query = f"SELECT DISTINCT source FROM {table_name} ORDER BY source"
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df['source'].tolist() if not df.empty else []

    def get_value(self, table_name, country, year, source):
        conn = sqlite3.connect(self.db_path)
        query = f"""
            SELECT value FROM {table_name}
            WHERE country = ? AND year = ? AND source = ?
        """
        df = pd.read_sql_query(query, conn, params=(country, year, source))
        conn.close()
        if not df.empty:
            return df.iloc[0]['value']
        return None

    def get_is_estimated(self, table_name, country, year, source):
        conn = sqlite3.connect(self.db_path)
        query = f"""
            SELECT is_estimated FROM {table_name}
            WHERE country = ? AND year = ? AND source = ?
        """
        df = pd.read_sql_query(query, conn, params=(country, year, source))
        conn.close()
        if not df.empty:
            return df.iloc[0]['is_estimated']
        return 1

    def get_all_years(self, country, table_name, source):
        conn = sqlite3.connect(self.db_path)
        query = f"""
            SELECT DISTINCT year FROM {table_name}
            WHERE country = ? AND source = ?
            ORDER BY year
        """
        df = pd.read_sql_query(query, conn, params=(country, source))
        conn.close()
        return df['year'].tolist()

    def get_country_list(self, table_name):
        conn = sqlite3.connect(self.db_path)
        query = f"SELECT DISTINCT country FROM {table_name} ORDER BY country"
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df['country'].tolist()

    def save_manual_record(self, country, year, katsayi_turu, value, source='manual'):
        table_map = {
            'gini': 'gini',
            'automation': 'automation',
            'governance': 'governance',
            'consciousness': 'consciousness',
            'resistance': 'resistance'
        }
        table = table_map.get(katsayi_turu)
        if not table:
            return False
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        # Önce aynı kayıt var mı kontrol et, varsa güncelle
        cursor.execute(f"""
            SELECT 1 FROM {table}
            WHERE country = ? AND year = ? AND source = ?
        """, (country, year, source))
        if cursor.fetchone():
            cursor.execute(f"""
                UPDATE {table}
                SET value = ?, is_estimated = 0
                WHERE country = ? AND year = ? AND source = ?
            """, (value, country, year, source))
        else:
            cursor.execute(f"""
                INSERT INTO {table} (country, year, value, source, is_estimated)
                VALUES (?, ?, ?, ?, 0)
            """, (country, year, value, source))
        conn.commit()
        conn.close()
        return True

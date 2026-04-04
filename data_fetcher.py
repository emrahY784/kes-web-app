import sqlite3
import pandas as pd
from datetime import datetime

class DataFetcher:
    def __init__(self, db_path='kes_data_unified.db'):
        self.db_path = db_path

    def get_available_sources(self, table_name):
        """Belirtilen tablodaki benzersiz kaynakları döndürür"""
        conn = sqlite3.connect(self.db_path)
        query = f"SELECT DISTINCT source FROM {table_name} ORDER BY source"
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df['source'].tolist() if not df.empty else []

    def get_value(self, table_name, country, year, source):
        """Belirtilen kaynaktan ilgili değeri alır"""
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

    def get_all_years(self, country, table_name, source):
        """Bir ülke ve kaynak için mevcut yılları döndürür"""
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
        """Tablodaki tüm ülkeleri döndürür (kaynak bağımsız)"""
        conn = sqlite3.connect(self.db_path)
        query = f"SELECT DISTINCT country FROM {table_name} ORDER BY country"
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df['country'].tolist()

    def save_manual_record(self, country, year, katsayi_turu, value, source='manual'):
        """Manuel girilen veriyi ilgili tabloya kaydeder"""
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
        # Varsa güncelle, yoksa ekle
        cursor.execute(f"""
            INSERT OR REPLACE INTO {table} (country, year, value, source)
            VALUES (?, ?, ?, ?)
        """, (country, year, value, source))
        conn.commit()
        conn.close()
        return True

    def get_manual_sources(self, table_name):
        """Manuel kaynakları da listeye ekler (eğer varsa)"""
        sources = self.get_available_sources(table_name)
        if 'manual' not in sources:
            sources.append('manual')
        return sources

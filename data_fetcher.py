import sqlite3
import pandas as pd

class DataFetcher:
    def __init__(self, db_path='new_kes_data.db'):
        self.db_path = db_path

    def get_available_sources(self, table_name):
        conn = sqlite3.connect(self.db_path)
        query = f"SELECT DISTINCT source FROM {table_name} ORDER BY source"
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df['source'].tolist() if not df.empty else []

    def get_sources_with_urls(self, table_name):
        """Kaynak adı ve URL bilgisini birlikte döndürür"""
        source_urls = {
            'original_unified': 'Kendi oluşturduğumuz unified veritabanı (Dünya Bankası + OWID + WGI + ILO)',
            'full_db_legacy': 'Eski full.db dosyası (Dünya Bankası + OWID + WGI + ILO)',
            'worldbank': 'https://api.worldbank.org/v2/country/all/indicator/SI.POV.GINI',
            'owid': 'https://ourworldindata.org/grapher/robot-density-in-manufacturing',
            'wgi': 'https://info.worldbank.org/governance/wgi/',
            'wgi_fixed': 'WGI verilerinin normalize edilmiş hali (0-100)',
            'worldbank_union': 'https://api.worldbank.org/v2/country/all/indicator/SL.UEM.TRDN.ZS',
            'wb_political_stability': 'https://api.worldbank.org/v2/country/all/indicator/PV.EST',
            'fsi': 'https://fragilestatesindex.org/',
            'gpr': 'https://www.matteoiacoviello.com/gpr.htm',
            'evi': 'https://www.un.org/development/desa/dpad/least-developed-country-category/evi.html',
            'vdem': 'https://www.v-dem.net/',
            'swiid': 'https://fsolt.org/swiid/',
            'ifr': 'https://ifr.org/',
            'manual': 'Kullanıcı tarafından manuel girilen veri'
        }
        sources = self.get_available_sources(table_name)
        result = []
        for src in sources:
            url = source_urls.get(src, 'Kaynak bilgisi mevcut değil')
            result.append({'source': src, 'url': url})
        return result

    def get_value(self, table_name, country, year, source):
        conn = sqlite3.connect(self.db_path)
        query = f"""
            SELECT value FROM {table_name}
            WHERE country = ? AND year = ? AND source = ?
        """
        df = pd.read_sql_query(query, conn, params=(country, year, source))
        conn.close()
        if not df.empty:
            return float(df.iloc[0]['value'])
        return None

    def get_value_with_info(self, table_name, country, year, source):
        """Değer, kullanılan yıl ve tahmini olup olmadığını döndürür"""
        conn = sqlite3.connect(self.db_path)
        query = f"""
            SELECT value, year, is_estimated FROM {table_name}
            WHERE country = ? AND source = ?
            ORDER BY ABS(year - ?) LIMIT 1
        """
        df = pd.read_sql_query(query, conn, params=(country, source, year))
        conn.close()
        if not df.empty:
            val = float(df.iloc[0]['value'])
            used_year = int(df.iloc[0]['year'])
            is_est = int(df.iloc[0]['is_estimated'])
            return val, used_year, is_est
        return 50.0, year, 1

    def get_all_years(self, country, table_name, source):
        conn = sqlite3.connect(self.db_path)
        query = f"""
            SELECT DISTINCT year FROM {table_name}
            WHERE country = ? AND source = ?
            ORDER BY year
        """
        df = pd.read_sql_query(query, conn, params=(country, source))
        conn.close()
        return [int(y) for y in df['year'].tolist()]

    def get_country_list(self, table_name):
        conn = sqlite3.connect(self.db_path)
        query = f"SELECT DISTINCT country FROM {table_name} ORDER BY country"
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df['country'].tolist()

    def get_max_year(self):
        """Tüm tablolardaki en büyük yılı bul"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(year) FROM gini_values")
        max_year = cursor.fetchone()[0]
        conn.close()
        return max_year if max_year else 2024

    def save_manual_record(self, country, year, katsayi_turu, value, source='manual'):
        table_map = {
            'gini': 'gini_values',
            'automation': 'automation_values',
            'governance': 'governance_values',
            'consciousness': 'consciousness_values',
            'resistance': 'resistance_values'
        }
        table = table_map.get(katsayi_turu)
        if not table:
            return False
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
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

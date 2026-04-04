import sqlite3
import pandas as pd
from datetime import datetime
import requests

class DataFetcher:
    def __init__(self, db_path='kes_data.db', world_bank_api_key=None):
        self.db_path = db_path
        self.world_bank_api_key = world_bank_api_key
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS country_data (
                country TEXT,
                year INTEGER,
                gini REAL,
                automation REAL,
                evcillestirme REAL,
                bilinc REAL,
                dis_direnc REAL,
                updated_at TEXT,
                PRIMARY KEY (country, year)
            )
        ''')
        conn.commit()
        conn.close()

    def _save_record(self, country, year, gini=None, automation=None, evcillestirme=None, bilinc=None, dis_direnc=None):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO country_data
            (country, year, gini, automation, evcillestirme, bilinc, dis_direnc, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (country, year, gini, automation, evcillestirme, bilinc, dis_direnc, datetime.now().isoformat()))
        conn.commit()
        conn.close()

    def load_to_dataframe(self):
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql_query("SELECT * FROM country_data", conn)
        conn.close()
        return df

    # World Bank API
    def fetch_world_bank_gini(self, country_code):
        url = f"http://api.worldbank.org/v2/country/{country_code}/indicator/SI.POV.GINI?format=json&per_page=100"
        try:
            response = requests.get(url)
            data = response.json()
            records = []
            for item in data[1]:
                year = int(item['date'])
                if item['value'] is not None:
                    records.append({'year': year, 'gini': float(item['value'])})
            return pd.DataFrame(records)
        except Exception as e:
            print(f"World Bank Gini hatası: {e}")
            return pd.DataFrame()

    # ILO API (automation - placeholder)
    def fetch_ilo_automation(self, country_code):
        # ILO API için anahtar gerekebilir, şimdilik boş
        return pd.DataFrame()

    # World Bank Government Effectiveness (evcilleştirme)
    def fetch_wb_governance(self, country_code):
        url = f"http://api.worldbank.org/v2/country/{country_code}/indicator/GE.EST?format=json&per_page=100"
        try:
            response = requests.get(url)
            data = response.json()
            records = []
            for item in data[1]:
                year = int(item['date'])
                if item['value'] is not None:
                    val = (float(item['value']) + 2.5) / 5 * 100
                    records.append({'year': year, 'evcillestirme': val})
            return pd.DataFrame(records)
        except:
            return pd.DataFrame()
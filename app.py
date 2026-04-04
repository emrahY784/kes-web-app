from flask import Flask, render_template, request, jsonify
import pandas as pd
import plotly.express as px
import plotly.utils
import json
import os
import traceback
from kes_calculator import KESCalculator
from data_fetcher import DataFetcher

app = Flask(__name__)

COUNTRIES = [
    {'code': 'TUR', 'name': 'Turkey'},
    {'code': 'USA', 'name': 'United States'},
    {'code': 'DEU', 'name': 'Germany'},
    {'code': 'CHN', 'name': 'China'},
    {'code': 'RUS', 'name': 'Russia'},
]

# Ülke adı -> kod eşlemesi (API için)
COUNTRY_NAME_TO_CODE = {
    'Turkey': 'TUR',
    'United States': 'USA',
    'Germany': 'DEU',
    'China': 'CHN',
    'Russia': 'RUS',
}

WORLD_BANK_API_KEY = os.environ.get('WORLD_BANK_API_KEY', None)

@app.route('/')
def index():
    try:
        return render_template('index.html', countries=COUNTRIES)
    except Exception as e:
        return f"<h1>Hata</h1><pre>{traceback.format_exc()}</pre>", 500

@app.route('/available_years', methods=['POST'])
def available_years():
    data = request.json
    country = data['country']
    fetcher = DataFetcher()
    df = fetcher.load_to_dataframe()
    df_country = df[df['country'] == country]
    years = sorted(df_country['year'].unique().tolist())
    return jsonify({'years': years})

@app.route('/calculate', methods=['POST'])
def calculate():
    data = request.json
    country = data['country']
    requested_year = int(data['year'])
    alpha = float(data.get('alpha', 0.5))
    beta = float(data.get('beta', 0.5))
    gamma = float(data.get('gamma', 0.5))
    lambd = float(data.get('lambd', 0.5))
    geometric = data.get('geometric', False)
    use_min = data.get('use_min', False)

    fetcher = DataFetcher(world_bank_api_key=WORLD_BANK_API_KEY)
    df = fetcher.load_to_dataframe()
    df_country = df[df['country'] == country]
    
    if df_country.empty:
        return jsonify({'error': f'{country} için hiç veri yok. Lütfen "API\'den Çek" veya "Manuel Veri Girişi" yapın.'}), 404

    # İstenen yıl varsa onu kullan, yoksa en yakın yılı bul
    if requested_year in df_country['year'].values:
        row = df_country[df_country['year'] == requested_year].iloc[0]
        used_year = requested_year
    else:
        df_country['year_diff'] = abs(df_country['year'] - requested_year)
        nearest = df_country.loc[df_country['year_diff'].idxmin()]
        used_year = int(nearest['year'])
        row = nearest

    # Eksik değerleri varsayılan değerlerle doldur (50 = nötr)
    gini = float(row['gini']) if pd.notna(row['gini']) else 50.0
    automation = float(row['automation']) if pd.notna(row['automation']) else 50.0
    evcillestirme = float(row['evcillestirme']) if pd.notna(row['evcillestirme']) else 50.0
    bilinc = float(row['bilinc']) if pd.notna(row['bilinc']) else 50.0
    dis_direnc = float(row['dis_direnc']) if pd.notna(row['dis_direnc']) else 50.0

    calc = KESCalculator(alpha=alpha, beta=beta, gamma=gamma, lambd=lambd,
                         geometric=geometric, use_min=use_min)
    v_ic = calc.calculate_v_ic(gini, automation, evcillestirme, bilinc)
    kes = calc.calculate_kes(v_ic, dis_direnc)

    return jsonify({
        'country': country,
        'used_year': used_year,
        'requested_year': requested_year,
        'v_ic_score': round(v_ic, 2),
        'kes': round(kes, 2),
        'interpretation': 'Sermayeci Kutup' if kes < 33 else ('Kamucu Kutup' if kes > 66 else 'Karma / Geçiş')
    })

@app.route('/trend', methods=['POST'])
def trend():
    try:
        data = request.json
        country = data['country']
        start_year = int(data.get('start_year', 2000))
        end_year = int(data.get('end_year', 2024))

        fetcher = DataFetcher()
        df = fetcher.load_to_dataframe()
        df_country = df[(df['country'] == country) & (df['year'] >= start_year) & (df['year'] <= end_year)]
        df_country = df_country.sort_values('year')
        if df_country.empty:
            return jsonify({'error': f'{country} için trend verisi yok'}), 404

        # Eksik değerleri doldur (NaN varsa)
        df_country['kes'] = df_country.apply(lambda row: calculate_kes_for_row(row), axis=1)
        
        fig = px.line(df_country, x='year', y='kes', title=f'{country} - KES Trendi',
                      labels={'kes': 'Kutup Eğilim Skoru', 'year': 'Yıl'},
                      markers=True)
        fig.add_hline(y=50, line_dash="dash", line_color="red")
        fig.update_layout(yaxis_range=[0,100])
        graph_json = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
        return jsonify({'graph': graph_json})
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': f'Sunucu hatası: {str(e)}'}), 500

def calculate_kes_for_row(row):
    calc = KESCalculator()
    v_ic = calc.calculate_v_ic(
        row.get('gini', 50), row.get('automation', 50),
        row.get('evcillestirme', 50), row.get('bilinc', 50)
    )
    return calc.calculate_kes(v_ic, row.get('dis_direnc', 50))

@app.route('/manual_data', methods=['POST'])
def manual_data():
    try:
        data = request.json
        country = data['country']
        year = int(data['year'])
        gini = float(data['gini'])
        automation = float(data['automation'])
        evcillestirme = float(data['evcillestirme'])
        bilinc = float(data['bilinc'])
        dis_direnc = float(data['dis_direnc'])

        fetcher = DataFetcher()
        fetcher._save_record(country, year, gini, automation, evcillestirme, bilinc, dis_direnc)
        return jsonify({'status': 'success', 'message': f'{country} {year} verisi kaydedildi.'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/fetch_from_api', methods=['POST'])
def fetch_from_api():
    data = request.json
    country_name = data['name']
    
    country_code = COUNTRY_TO_CODE.get(country_name)
    if not country_code:
        return jsonify({'error': f'"{country_name}" için kod bulunamadı.'}), 400

    fetcher = DataFetcher(world_bank_api_key=WORLD_BANK_API_KEY)
    
    # Gini verilerini çek
    gini_df = fetcher.fetch_world_bank_gini(country_code)
    for _, row in gini_df.iterrows():
        # automation ve bilinc için varsayılan 50, dis_direnc için de 50 (manuel girilmesi gerekir)
        fetcher._save_record(country_name, row['year'], 
                             gini=row['gini'], 
                             automation=50.0, 
                             evcillestirme=None, 
                             bilinc=50.0, 
                             dis_direnc=50.0)
    
    # Yönetişim verilerini çek (evcillestirme)
    gov_df = fetcher.fetch_wb_governance(country_code)
    for _, row in gov_df.iterrows():
        # Önce bu yıl için varsa kaydı güncelle, yoksa yeni oluştur
        fetcher._save_record(country_name, row['year'], 
                             evcillestirme=row['evcillestirme'],
                             automation=50.0,
                             bilinc=50.0,
                             dis_direnc=50.0)
    
    return jsonify({'status': 'success', 'message': f'{country_name} verileri güncellendi. NOT: Otomasyon ve Bilinç için varsayılan (50) değeri kullanıldı. Gerçek değerler için "Manuel Veri Girişi" yapınız.'})

@app.route('/debug_db')
def debug_db():
    fetcher = DataFetcher()
    df = fetcher.load_to_dataframe()
    return df.to_html()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

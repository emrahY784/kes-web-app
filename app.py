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

WORLD_BANK_API_KEY = os.environ.get('WORLD_BANK_API_KEY', None)

@app.route('/')
def index():
    try:
        return render_template('index.html', countries=COUNTRIES)
    except Exception as e:
        return f"<h1>Hata</h1><pre>{traceback.format_exc()}</pre>", 500

# Bir ülke için mevcut yılları döndürür
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
        # En yakın yılı bul
        df_country['year_diff'] = abs(df_country['year'] - requested_year)
        nearest = df_country.loc[df_country['year_diff'].idxmin()]
        used_year = int(nearest['year'])
        row = nearest

    gini = row['gini']
    automation = row['automation']
    evcillestirme = row['evcillestirme']
    bilinc = row['bilinc']
    dis_direnc = row['dis_direnc']

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

    fig = px.line(df_country, x='year', y='kes', title=f'{country} - KES Trendi',
                  labels={'kes': 'Kutup Eğilim Skoru', 'year': 'Yıl'},
                  markers=True)
    fig.add_hline(y=50, line_dash="dash", line_color="red")
    fig.update_layout(yaxis_range=[0,100])
    graph_json = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    return jsonify({'graph': graph_json})

@app.route('/manual_data', methods=['POST'])
def manual_data():
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

@app.route('/fetch_from_api', methods=['POST'])
def fetch_from_api():
    data = request.json
    country_code = data.get('code')
    country_name = data.get('name')
    
    # Eğer sadece name gönderildiyse, kodu bul
    if not country_code and country_name:
        code_map = {c['name']: c['code'] for c in COUNTRIES}
        country_code = code_map.get(country_name)
        if not country_code:
            return jsonify({'error': f'{country_name} için ülke kodu bulunamadı.'}), 400
        country_name = country_name
    elif not country_code or not country_name:
        return jsonify({'error': 'Lütfen hem ülke kodu hem de ülke adı girin.'}), 400

    fetcher = DataFetcher(world_bank_api_key=WORLD_BANK_API_KEY)
    
    # Gini verilerini çek
    gini_df = fetcher.fetch_world_bank_gini(country_code)
    gini_count = 0
    for _, row in gini_df.iterrows():
        fetcher._save_record(country_name, row['year'], gini=row['gini'])
        gini_count += 1
    
    # Yönetişim verilerini çek
    gov_df = fetcher.fetch_wb_governance(country_code)
    gov_count = 0
    for _, row in gov_df.iterrows():
        fetcher._save_record(country_name, row['year'], evcillestirme=row['evcillestirme'])
        gov_count += 1
    
    if gini_count == 0 and gov_count == 0:
        return jsonify({'error': f'{country_name} için API\'den veri alınamadı. Ülke kodu "{country_code}" geçerli mi?'}), 404
    
    return jsonify({'status': 'success', 'message': f'{country_name} için {gini_count} Gini, {gov_count} yönetişim kaydı eklendi/güncellendi.'})

@app.route('/debug_db')
def debug_db():
    fetcher = DataFetcher()
    df = fetcher.load_to_dataframe()
    if df.empty:
        return "Veritabanı boş."
    return df.to_html()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

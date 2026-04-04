from flask import Flask, render_template, request, jsonify
import pandas as pd
import plotly.express as px
import plotly.utils
import json
import os
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

# World Bank API anahtarı (opsiyonel, environment variable'dan al)
WORLD_BANK_API_KEY = os.environ.get('WORLD_BANK_API_KEY', None)

@app.route('/')
def index():
    return render_template('index.html', countries=COUNTRIES)

@app.route('/calculate', methods=['POST'])
def calculate():
    data = request.json
    country = data['country']
    year = int(data['year'])
    alpha = float(data.get('alpha', 0.5))
    beta = float(data.get('beta', 0.5))
    gamma = float(data.get('gamma', 0.5))
    lambd = float(data.get('lambd', 0.5))
    geometric = data.get('geometric', False)
    use_min = data.get('use_min', False)

    fetcher = DataFetcher(world_bank_api_key=WORLD_BANK_API_KEY)
    df = fetcher.load_to_dataframe()
    row = df[(df['country'] == country) & (df['year'] == year)]
    if row.empty:
        return jsonify({'error': f'{country} - {year} için veri bulunamadı. Lütfen "Manuel Veri Girişi" sekmesinden ekleyin.'}), 404

    gini = row['gini'].values[0]
    automation = row['automation'].values[0]
    evcillestirme = row['evcillestirme'].values[0]
    bilinc = row['bilinc'].values[0]
    dis_direnc = row['dis_direnc'].values[0]

    calc = KESCalculator(alpha=alpha, beta=beta, gamma=gamma, lambd=lambd,
                         geometric=geometric, use_min=use_min)
    v_ic = calc.calculate_v_ic(gini, automation, evcillestirme, bilinc)
    kes = calc.calculate_kes(v_ic, dis_direnc)

    return jsonify({
        'country': country,
        'year': year,
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
    country_code = data['code']
    country_name = data['name']

    fetcher = DataFetcher(world_bank_api_key=WORLD_BANK_API_KEY)
    gini_df = fetcher.fetch_world_bank_gini(country_code)
    for _, row in gini_df.iterrows():
        fetcher._save_record(country_name, row['year'], gini=row['gini'])
    
    gov_df = fetcher.fetch_wb_governance(country_code)
    for _, row in gov_df.iterrows():
        fetcher._save_record(country_name, row['year'], evcillestirme=row['evcillestirme'])
    
    return jsonify({'status': 'success', 'message': f'{country_name} verileri güncellendi.'})
    
@app.route('/test')
def test():
    return "Uygulama çalışıyor!", 200
    
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

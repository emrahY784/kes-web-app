from flask import Flask, render_template, request, jsonify
import pandas as pd
import plotly.express as px
import plotly.utils
import json
import traceback
from kes_calculator import KESCalculator
from data_fetcher import DataFetcher

app = Flask(__name__)

DATABASE_PATH = 'final_kes_data.db'  # Kendi veritabanı adınız

TABLES = {
    'gini_values': 'Gini Katsayısı',
    'automation_values': 'Otomasyon',
    'governance_values': 'Evcilleştirme Kapasitesi',
    'consciousness_values': 'Toplumsal Bilinç',
    'resistance_values': 'Dış Direnç'
}

@app.route('/')
def index():
    return render_template('index.html', tables=TABLES)

@app.route('/get_countries')
def get_countries():
    fetcher = DataFetcher(DATABASE_PATH)
    countries = fetcher.get_country_list('gini_values')
    return jsonify(countries)

@app.route('/get_max_year')
def get_max_year():
    fetcher = DataFetcher(DATABASE_PATH)
    max_year = fetcher.get_max_year()
    return jsonify({'max_year': max_year})

@app.route('/get_sources', methods=['POST'])
def get_sources():
    data = request.json
    table = data.get('table')
    fetcher = DataFetcher(DATABASE_PATH)
    sources = fetcher.get_available_sources(table)
    if 'manual' not in sources:
        sources.append('manual')
    return jsonify(sources)

@app.route('/get_value', methods=['POST'])
def get_value():
    data = request.json
    table = data['table']
    country = data['country']
    year = int(data['year'])
    source = data['source']
    fetcher = DataFetcher(DATABASE_PATH)
    val, used_year, is_est = fetcher.get_value_with_info(table, country, year, source)
    return jsonify({'value': round(val, 2) if val else 50, 'used_year': used_year, 'estimated': is_est})

@app.route('/calculate', methods=['POST'])
def calculate():
    try:
        data = request.json
        country = data['country']
        year = int(data['year'])
        sources = data.get('sources', {})
        alpha = float(data.get('alpha', 0.5))
        beta = float(data.get('beta', 0.5))
        gamma = float(data.get('gamma', 0.5))
        lambd = float(data.get('lambd', 0.5))
        geometric = data.get('geometric', False)
        use_min = data.get('use_min', False)

        fetcher = DataFetcher(DATABASE_PATH)

        def get_val(table, source):
            val, used_year, is_est = fetcher.get_value_with_info(table, country, year, source)
            return val, used_year, is_est

        gini, gini_year, gini_est = get_val('gini_values', sources.get('gini_values', 'original_unified'))
        automation, auto_year, auto_est = get_val('automation_values', sources.get('automation_values', 'original_unified'))
        governance, gov_year, gov_est = get_val('governance_values', sources.get('governance_values', 'original_unified'))
        consciousness, con_year, con_est = get_val('consciousness_values', sources.get('consciousness_values', 'original_unified'))
        resistance, res_year, res_est = get_val('resistance_values', sources.get('resistance_values', 'original_unified'))

        estimated = {
            'gini_values': gini_est,
            'automation_values': auto_est,
            'governance_values': gov_est,
            'consciousness_values': con_est,
            'resistance_values': res_est
        }

        calc = KESCalculator(alpha, beta, gamma, lambd, geometric, use_min)
        v_ic = calc.calculate_v_ic(gini, automation, governance, consciousness)
        kes = calc.calculate_kes(v_ic, resistance)

        response = {
            'status': 'success',
            'kes': round(kes, 2),
            'v_ic': round(v_ic, 2),
            'v_dis': round(resistance, 2),
            'interpretation': 'Sermayeci Kutup' if kes < 33 else ('Kamucu Kutup' if kes > 66 else 'Karma / Geçiş'),
            'used_years': {
                'gini_values': gini_year,
                'automation_values': auto_year,
                'governance_values': gov_year,
                'consciousness_values': con_year,
                'resistance_values': res_year
            },
            'estimated': estimated
        }
        return jsonify(response)
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e), 'traceback': traceback.format_exc()}), 500

@app.route('/trend', methods=['POST'])
def trend():
    try:
        data = request.json
        country = data['country']
        start_year = int(data.get('start_year', 2000))
        end_year = int(data.get('end_year', 2024))
        fetcher = DataFetcher(DATABASE_PATH)

        # Trend için resistance tablosundaki ilk kaynağı bul (original_unified yoksa)
        sources = fetcher.get_available_sources('resistance_values')
        if not sources:
            return jsonify({'error': 'Dış direnç için kaynak bulunamadı'}), 404
        default_source = sources[0]

        results = []
        for year in range(start_year, end_year + 1):
            gini = fetcher.get_value('gini_values', country, year, 'original_unified')
            auto = fetcher.get_value('automation_values', country, year, 'original_unified')
            gov = fetcher.get_value('governance_values', country, year, 'original_unified')
            con = fetcher.get_value('consciousness_values', country, year, 'original_unified')
            res = fetcher.get_value('resistance_values', country, year, default_source)
            if None in [gini, auto, gov, con, res]:
                continue
            calc = KESCalculator()
            v_ic = calc.calculate_v_ic(gini, auto, gov, con)
            kes = calc.calculate_kes(v_ic, res)
            results.append({'year': year, 'kes': round(kes, 2)})

        if not results:
            return jsonify({'error': f'{country} için {start_year}-{end_year} aralığında trend verisi yok.'}), 404

        df = pd.DataFrame(results)
        fig = px.line(df, x='year', y='kes', title=f'{country} - KES Trendi',
                      markers=True, labels={'kes': 'KES', 'year': 'Yıl'})
        fig.add_hline(y=50, line_dash="dash", line_color="red")
        fig.update_layout(yaxis_range=[0,100])
        graph_json = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
        return jsonify({'graph': graph_json})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/manual_data', methods=['POST'])
def manual_data():
    try:
        data = request.json
        country = data['country']
        year = int(data['year'])
        katsayi_turu = data['katsayi_turu']
        value = float(data['value'])
        fetcher = DataFetcher(DATABASE_PATH)
        success = fetcher.save_manual_record(country, year, katsayi_turu, value)
        if success:
            return jsonify({'status': 'success', 'message': f'{country} {year} için {katsayi_turu} kaydedildi.'})
        else:
            return jsonify({'status': 'error', 'message': 'Kayıt başarısız'}), 500
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)

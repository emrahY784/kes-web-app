from flask import Flask, render_template, request, jsonify, session
import pandas as pd
import plotly.express as px
import plotly.utils
import json
import traceback
import os
from kes_calculator import KESCalculator
from data_fetcher import DataFetcher

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this'

# Varsayılan veritabanı dosyası
DATABASE_PATH = 'kes_data_unified.db'

# Tablo isimleri ve görünen adları
TABLES = {
    'gini': 'Gini Katsayısı',
    'automation': 'Otomasyon',
    'governance': 'Evcilleştirme Kapasitesi',
    'consciousness': 'Toplumsal Bilinç',
    'resistance': 'Dış Direnç'
}

@app.route('/')
def index():
    return render_template('index.html', tables=TABLES)

@app.route('/get_countries')
def get_countries():
    """Tüm ülkelerin listesini döndürür (gini tablosundan)"""
    fetcher = DataFetcher(DATABASE_PATH)
    countries = fetcher.get_country_list('gini')
    return jsonify(countries)

@app.route('/get_sources', methods=['POST'])
def get_sources():
    """Bir tablo için mevcut kaynakları döndürür"""
    data = request.json
    table = data.get('table')
    fetcher = DataFetcher(DATABASE_PATH)
    sources = fetcher.get_manual_sources(table)
    return jsonify(sources)

@app.route('/get_available_years', methods=['POST'])
def get_available_years():
    """Bir ülke, tablo ve kaynak için mevcut yılları döndürür"""
    data = request.json
    country = data.get('country')
    table = data.get('table')
    source = data.get('source')
    fetcher = DataFetcher(DATABASE_PATH)
    years = fetcher.get_all_years(country, table, source)
    return jsonify(years)

@app.route('/calculate', methods=['POST'])
def calculate():
    try:
        data = request.json
        country = data['country']
        year = int(data['year'])
        # Seçilen kaynaklar
        sources = data.get('sources', {})
        gini_source = sources.get('gini', 'worldbank')
        automation_source = sources.get('automation', 'owid')
        governance_source = sources.get('governance', 'wgi')
        consciousness_source = sources.get('consciousness', 'worldbank_union')
        resistance_source = sources.get('resistance', 'wb_political_stability')
        # Ağırlıklar
        alpha = float(data.get('alpha', 0.5))
        beta = float(data.get('beta', 0.5))
        gamma = float(data.get('gamma', 0.5))
        lambd = float(data.get('lambd', 0.5))
        geometric = data.get('geometric', False)
        use_min = data.get('use_min', False)

        fetcher = DataFetcher(DATABASE_PATH)

        def get_val(table, source):
            val = fetcher.get_value(table, country, year, source)
            if val is None:
                # En yakın yılı bulmaya çalış
                years = fetcher.get_all_years(country, table, source)
                if years:
                    nearest = min(years, key=lambda y: abs(y - year))
                    val = fetcher.get_value(table, country, nearest, source)
                    return val, nearest
            return val, year

        gini, gini_year = get_val('gini', gini_source)
        automation, auto_year = get_val('automation', automation_source)
        governance, gov_year = get_val('governance', governance_source)
        consciousness, con_year = get_val('consciousness', consciousness_source)
        resistance, res_year = get_val('resistance', resistance_source)

        # Eksik değerleri 50 ile doldur
        gini = gini if gini is not None else 50.0
        automation = automation if automation is not None else 50.0
        governance = governance if governance is not None else 50.0
        consciousness = consciousness if consciousness is not None else 50.0
        resistance = resistance if resistance is not None else 50.0

        calc = KESCalculator(alpha, beta, gamma, lambd, geometric, use_min)
        v_ic = calc.calculate_v_ic(gini, automation, governance, consciousness)
        kes = calc.calculate_kes(v_ic, resistance)

        return jsonify({
            'status': 'success',
            'kes': round(kes, 2),
            'v_ic': round(v_ic, 2),
            'interpretation': 'Sermayeci Kutup' if kes < 33 else ('Kamucu Kutup' if kes > 66 else 'Karma / Geçiş'),
            'used_years': {
                'gini': gini_year,
                'automation': auto_year,
                'governance': gov_year,
                'consciousness': con_year,
                'resistance': res_year
            }
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e), 'traceback': traceback.format_exc()}), 500

@app.route('/trend', methods=['POST'])
def trend():
    try:
        data = request.json
        country = data['country']
        start_year = int(data.get('start_year', 2000))
        end_year = int(data.get('end_year', 2024))
        # Trend için varsayılan kaynakları kullan (ilk mevcut kaynak)
        fetcher = DataFetcher(DATABASE_PATH)
        # resistance tablosundaki ilk kaynağı al
        sources = fetcher.get_manual_sources('resistance')
        default_source = sources[0] if sources else 'wb_political_stability'

        # Yıllara göre KES hesapla
        results = []
        for year in range(start_year, end_year + 1):
            gini = fetcher.get_value('gini', country, year, 'worldbank')
            auto = fetcher.get_value('automation', country, year, 'owid')
            gov = fetcher.get_value('governance', country, year, 'wgi')
            con = fetcher.get_value('consciousness', country, year, 'worldbank_union')
            res = fetcher.get_value('resistance', country, year, default_source)
            if None in [gini, auto, gov, con, res]:
                continue
            calc = KESCalculator()
            v_ic = calc.calculate_v_ic(gini, auto, gov, con)
            kes = calc.calculate_kes(v_ic, res)
            results.append({'year': year, 'kes': kes})

        if not results:
            return jsonify({'error': 'Trend için yeterli veri yok'}), 404

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
    data = request.json
    country = data['country']
    year = int(data['year'])
    katsayi_turu = data['katsayi_turu']  # 'gini', 'automation', etc.
    value = float(data['value'])
    fetcher = DataFetcher(DATABASE_PATH)
    success = fetcher.save_manual_record(country, year, katsayi_turu, value)
    if success:
        return jsonify({'status': 'success', 'message': f'{country} {year} için {katsayi_turu} kaydedildi.'})
    else:
        return jsonify({'status': 'error', 'message': 'Kayıt başarısız'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)

from flask import Flask, render_template, request, jsonify
import pandas as pd
import plotly.express as px
import plotly.utils
import json
import traceback
from kes_calculator import KESCalculator
from data_fetcher import DataFetcher

app = Flask(__name__)

# Varsayılan veritabanı dosyası (yeni yapıdaki final dosya)
DATABASE_PATH = 'final_kes_data.db'

# Tablo isimleri ve görünen adları (frontend'e gönderilecek)
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
    """Tüm ülkelerin listesini döndürür (gini_values tablosundan)"""
    fetcher = DataFetcher(DATABASE_PATH)
    countries = fetcher.get_country_list('gini_values')
    return jsonify(countries)

@app.route('/get_sources', methods=['POST'])
def get_sources():
    """Bir tablo için mevcut kaynakları döndürür"""
    data = request.json
    table = data.get('table')
    fetcher = DataFetcher(DATABASE_PATH)
    sources = fetcher.get_available_sources(table)
    # Manuel kaynağı da ekle (kullanıcı manuel giriş yapabilir)
    if 'manual' not in sources:
        sources.append('manual')
    return jsonify(sources)

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
            val = fetcher.get_value(table, country, year, source)
            used_year = year
            is_estimated = 0
            if val is None:
                # En yakın yılı bul
                years = fetcher.get_all_years(country, table, source)
                if years:
                    used_year = min(years, key=lambda y: abs(y - year))
                    val = fetcher.get_value(table, country, used_year, source)
                if val is None:
                    val = 50.0
                    is_estimated = 1
            else:
                # Değer var ama is_estimated kontrolü
                is_estimated = fetcher.get_is_estimated(table, country, used_year, source)
            return val, used_year, is_estimated

        gini, gini_year, gini_est = get_val('gini_values', sources.get('gini_values', 'worldbank'))
        automation, auto_year, auto_est = get_val('automation_values', sources.get('automation_values', 'owid'))
        governance, gov_year, gov_est = get_val('governance_values', sources.get('governance_values', 'wgi'))
        consciousness, con_year, con_est = get_val('consciousness_values', sources.get('consciousness_values', 'worldbank_union'))
        resistance, res_year, res_est = get_val('resistance_values', sources.get('resistance_values', 'wb_political_stability'))

        estimated = {
            'gini': gini_est,
            'automation': auto_est,
            'governance': gov_est,
            'consciousness': con_est,
            'resistance': res_est
        }

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
            },
            'estimated': estimated
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
        fetcher = DataFetcher(DATABASE_PATH)
        # Trend için varsayılan kaynakları kullan (ilk mevcut kaynak)
        sources = fetcher.get_available_sources('resistance_values')
        default_source = sources[0] if sources else 'wb_political_stability'

        results = []
        for year in range(start_year, end_year + 1):
            gini = fetcher.get_value('gini_values', country, year, 'worldbank')
            auto = fetcher.get_value('automation_values', country, year, 'owid')
            gov = fetcher.get_value('governance_values', country, year, 'wgi')
            con = fetcher.get_value('consciousness_values', country, year, 'worldbank_union')
            res = fetcher.get_value('resistance_values', country, year, default_source)
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

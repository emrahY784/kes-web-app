from flask import Flask, render_template, request, jsonify
import pandas as pd
import plotly.express as px
import plotly.utils
import json
import traceback
from kes_calculator import KESCalculator
from data_fetcher import DataFetcher

app = Flask(__name__)

@app.route('/')
def index():
    # Artık ülke listesi göndermiyoruz, manuel giriş yapılacak
    return render_template('index.html')

@app.route('/available_years', methods=['POST'])
def available_years():
    try:
        data = request.json
        country = data.get('country')
        if not country:
            return jsonify({'error': 'Ülke adı gerekli'}), 400
        
        fetcher = DataFetcher()
        df = fetcher.load_to_dataframe()
        if df.empty:
            return jsonify({'years': []})
        
        df_country = df[df['country'] == country]
        years = sorted(df_country['year'].dropna().unique().tolist())
        return jsonify({'years': years})
    except Exception as e:
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500

@app.route('/calculate', methods=['POST'])
def calculate():
    try:
        data = request.json
        country = data['country']
        requested_year = int(data['year'])
        alpha = float(data.get('alpha', 0.5))
        beta = float(data.get('beta', 0.5))
        gamma = float(data.get('gamma', 0.5))
        lambd = float(data.get('lambd', 0.5))
        geometric = data.get('geometric', False)
        use_min = data.get('use_min', False)

        fetcher = DataFetcher()
        df = fetcher.load_to_dataframe()
        df_country = df[df['country'] == country]
        
        if df_country.empty:
            return jsonify({'error': f'{country} için hiç veri yok. Lütfen "Manuel Veri Girişi" sekmesinden ekleyin.'}), 404

        if requested_year in df_country['year'].values:
            row = df_country[df_country['year'] == requested_year].iloc[0]
            used_year = requested_year
        else:
            df_country['year_diff'] = abs(df_country['year'] - requested_year)
            nearest = df_country.loc[df_country['year_diff'].idxmin()]
            used_year = int(nearest['year'])
            row = nearest

        warnings = []
        gini = row['gini'] if pd.notna(row['gini']) else 50.0
        if pd.isna(row['gini']): warnings.append("Gini eksik, varsayılan 50 kullanıldı.")
        automation = row['automation'] if pd.notna(row['automation']) else 50.0
        if pd.isna(row['automation']): warnings.append("Otomasyon eksik, varsayılan 50 kullanıldı.")
        evcillestirme = row['evcillestirme'] if pd.notna(row['evcillestirme']) else 50.0
        if pd.isna(row['evcillestirme']): warnings.append("Evcilleştirme eksik, varsayılan 50 kullanıldı.")
        bilinc = row['bilinc'] if pd.notna(row['bilinc']) else 50.0
        if pd.isna(row['bilinc']): warnings.append("Bilinç eksik, varsayılan 50 kullanıldı.")
        dis_direnc = row['dis_direnc'] if pd.notna(row['dis_direnc']) else 50.0
        if pd.isna(row['dis_direnc']): warnings.append("Dış direnç eksik, varsayılan 50 kullanıldı.")

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
            'interpretation': 'Sermayeci Kutup' if kes < 33 else ('Kamucu Kutup' if kes > 66 else 'Karma / Geçiş'),
            'warnings': warnings
        })
    except Exception as e:
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500

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

        if 'kes' not in df_country.columns:
            kes_list = []
            for _, row in df_country.iterrows():
                g = row['gini'] if pd.notna(row['gini']) else 50
                o = row['automation'] if pd.notna(row['automation']) else 50
                e = row['evcillestirme'] if pd.notna(row['evcillestirme']) else 50
                b = row['bilinc'] if pd.notna(row['bilinc']) else 50
                d = row['dis_direnc'] if pd.notna(row['dis_direnc']) else 50
                calc = KESCalculator()
                v_ic = calc.calculate_v_ic(g, o, e, b)
                kes_list.append(calc.calculate_kes(v_ic, d))
            df_country['kes'] = kes_list

        fig = px.line(df_country, x='year', y='kes', title=f'{country} - KES Trendi',
                      labels={'kes': 'Kutup Eğilim Skoru', 'year': 'Yıl'},
                      markers=True)
        fig.add_hline(y=50, line_dash="dash", line_color="red")
        fig.update_layout(yaxis_range=[0,100])
        graph_json = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
        return jsonify({'graph': graph_json})
    except Exception as e:
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500

@app.route('/manual_data', methods=['POST'])
def manual_data():
    try:
        data = request.json
        country = data['country']
        year = int(data['year'])
        gini = float(data['gini']) if data['gini'] is not None else None
        automation = float(data['automation']) if data['automation'] is not None else None
        evcillestirme = float(data['evcillestirme']) if data['evcillestirme'] is not None else None
        bilinc = float(data['bilinc']) if data['bilinc'] is not None else None
        dis_direnc = float(data['dis_direnc']) if data['dis_direnc'] is not None else None

        fetcher = DataFetcher()
        fetcher._save_record(country, year, gini, automation, evcillestirme, bilinc, dis_direnc)
        return jsonify({'status': 'success', 'message': f'{country} {year} verisi kaydedildi.'})
    except Exception as e:
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500

@app.route('/debug_db')
def debug_db():
    fetcher = DataFetcher()
    df = fetcher.load_to_dataframe()
    if df.empty:
        return "Veritabanı boş. Lütfen 'Manuel Veri Girişi' ile veri ekleyin."
    return df.to_html()

@app.errorhandler(Exception)
def handle_exception(e):
    return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)

import streamlit as st
import pandas as pd
import os
import io

# Configuración de la página
st.set_page_config(page_title="Dashboard de Cobertura de Stock", layout="wide")
st.title("📦 Análisis de Cobertura y Faltantes de Stock")


@st.cache_data
def cargar_datos():
    try:
        # 0. Cargar Maestro de Tiendas y Zonas (FILTRO PRINCIPAL)
        df_tiendas_zona = pd.read_excel('tiendas.xlsx')
        df_tiendas_zona.columns = ['Tienda', 'Zona']  # A: Tienda, B: REGION (como zona)
        lista_tiendas_permitidas = df_tiendas_zona['Tienda'].unique()

        # 1. Cargar Sectores Tienda
        df_sec_tienda = pd.read_excel('SectoresTienda.xlsx')
        df_sec_tienda.columns = df_sec_tienda.columns.str.strip()
        df_sec_tienda.rename(columns=lambda x: x.lower(), inplace=True)
        df_sec_tienda.rename(columns={'tienda': 'Tienda', 'sector tienda': 'Sector', 'amplitud tienda': 'Amplitud'},
                             inplace=True)

        # Filtrar solo tiendas del excel "tiendas"
        df_sec_tienda = df_sec_tienda[df_sec_tienda['Tienda'].isin(lista_tiendas_permitidas)]

        # 1.5 Cargar Sectores Articulos
        df_sec_art = pd.read_excel('SectoresArticulos.xlsx')
        df_sec_art.columns = df_sec_art.columns.str.strip()
        df_sec_art.rename(columns=lambda x: x.title(), inplace=True)

        # Cruzar para obtener el Alta
        df_alta = pd.merge(df_sec_tienda, df_sec_art, on=['Sector', 'Amplitud'], how='inner')

        # 2. Cargar Familias
        df_familias = pd.read_excel('Familias.xlsx')
        df_familias = df_familias.iloc[:, :2]
        df_familias.columns = ['Articulo', 'Familia']

        # Asignar la familia
        df_alta = pd.merge(df_alta, df_familias, on='Articulo', how='left')
        df_alta['Familia'] = df_alta['Familia'].fillna('SIN FAMILIA')

        # 3. Cargar los CSV de Stock
        bases_stock = []
        for i in range(1, 5):
            archivo = f'base{i}.csv'
            if os.path.exists(archivo):
                try:
                    df_base = pd.read_csv(archivo, sep=None, engine='python', encoding='utf-8-sig')
                except:
                    df_base = pd.read_csv(archivo, sep=None, engine='python')

                df_base.columns = df_base.columns.str.strip()
                cols_dict = {}
                for col in df_base.columns:
                    col_limpia = col.replace('\ufeff', '').lower()
                    if col_limpia == 'tienda':
                        cols_dict[col] = 'Tienda'
                    elif col_limpia in ['articulo', 'artículo']:
                        cols_dict[col] = 'Articulo'
                    elif 'stock cet' in col_limpia:
                        cols_dict[col] = 'Stock Cet'

                df_base.rename(columns=cols_dict, inplace=True)
                columnas_necesarias = ['Tienda', 'Articulo', 'Stock Cet']
                if all(c in df_base.columns for c in columnas_necesarias):
                    # Filtrar stock solo para tiendas permitidas
                    df_base = df_base[df_base['Tienda'].isin(lista_tiendas_permitidas)]
                    bases_stock.append(df_base[columnas_necesarias])

        if bases_stock:
            df_stock = pd.concat(bases_stock, ignore_index=True)
            for col in ['Tienda', 'Articulo']:
                df_stock[col] = pd.to_numeric(df_stock[col], errors='coerce')
                df_alta[col] = pd.to_numeric(df_alta[col], errors='coerce')

            df_stock = df_stock.groupby(['Tienda', 'Articulo'], as_index=False)['Stock Cet'].sum()
            return df_alta, df_stock, df_tiendas_zona
        else:
            return df_alta, pd.DataFrame(columns=['Tienda', 'Articulo', 'Stock Cet']), df_tiendas_zona

    except Exception as e:
        st.error(f"Error crítico al cargar datos o filtrar por tiendas: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()


# Función para Excel
def generar_excel(df_resumen):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_resumen.to_excel(writer, index=False, sheet_name='Resumen_Familias')
        workbook = writer.book
        header_format = workbook.add_format({'bold': True, 'bg_color': '#D7E4BC', 'border': 1})
        worksheet = writer.sheets['Resumen_Familias']
        for col_num, value in enumerate(df_resumen.columns.values):
            worksheet.write(0, col_num, value, header_format)
            worksheet.set_column(col_num, col_num, 20)
    return output.getvalue()


# --- EJECUCIÓN ---
df_alta_total, df_stock_total, df_zonas = cargar_datos()

if not df_alta_total.empty:
    tiendas_disponibles = sorted(df_alta_total['Tienda'].dropna().unique())
    opciones_selector = ["Todas las tiendas"] + [int(t) for t in tiendas_disponibles]
    tienda_seleccionada = st.selectbox("Selecciona una Tienda (Filtro por excel 'tiendas' aplicado)", opciones_selector)

    st.markdown("---")

    # PROCESAMIENTO
    if tienda_seleccionada == "Todas las tiendas":
        alta_tienda = df_alta_total.copy()
        stock_tienda = df_stock_total.copy()
    else:
        alta_tienda = df_alta_total[df_alta_total['Tienda'] == tienda_seleccionada].copy()
        stock_tienda = df_stock_total[df_stock_total['Tienda'] == tienda_seleccionada].copy()

    # Cruce Operativo
    df_analisis = pd.merge(alta_tienda, stock_tienda[['Tienda', 'Articulo', 'Stock Cet']], on=['Tienda', 'Articulo'],
                           how='left')
    df_analisis['Stock Cet'] = pd.to_numeric(df_analisis['Stock Cet'], errors='coerce').fillna(0)
    df_analisis['Con Stock'] = df_analisis['Stock Cet'] > 0

    # Pegar Zona
    df_analisis = pd.merge(df_analisis, df_zonas, on='Tienda', how='left')

    # KPIs
    total_articulos_alta = len(df_analisis)
    articulos_con_stock = df_analisis['Con Stock'].sum()
    articulos_faltantes = total_articulos_alta - articulos_con_stock
    cobertura_pct = (articulos_con_stock / total_articulos_alta * 100) if total_articulos_alta > 0 else 0

    st.subheader(f"Resumen Operativo: {tienda_seleccionada}")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Impactos de Alta", f"{total_articulos_alta:,}")
    col2.metric("Impactos con Stock", f"{articulos_con_stock:,}")
    col3.metric("Cobertura (%)", f"{cobertura_pct:.1f} %")
    col4.metric("Huecos Totales", f"{articulos_faltantes:,}")

    # --- SECCIÓN 1: FAMILIAS ---
    st.markdown("---")
    resumen_familia = df_analisis.groupby('Familia').agg(Alta_Total=('Articulo', 'count'),
                                                         Con_Stock=('Con Stock', 'sum')).reset_index()
    resumen_familia['Faltantes'] = resumen_familia['Alta_Total'] - resumen_familia['Con_Stock']
    resumen_familia['Cobertura (%)'] = (resumen_familia['Con_Stock'] / resumen_familia['Alta_Total'] * 100).round(1)
    resumen_familia = resumen_familia.sort_values('Faltantes', ascending=False)

    col_t, col_b = st.columns([3, 1])
    with col_t:
        st.subheader("📊 1. ¿Qué Familias fallan?")
    with col_b:
        st.download_button("📥 Excel Familias", generar_excel(resumen_familia), f"Cobertura_{tienda_seleccionada}.xlsx")

    st.dataframe(resumen_familia, column_config={
        "Cobertura (%)": st.column_config.ProgressColumn(format="%f%%", min_value=0, max_value=100)}, hide_index=True,
                 use_container_width=True)

    # --- SECCIÓN 2: ¿QUÉ ARTÍCULOS? (SOLO PARA "TODAS LAS TIENDAS") ---
    if tienda_seleccionada == "Todas las tiendas":
        st.markdown("---")
        st.subheader("🕵️ 2. ¿Qué artículos están faltando más? (Top Faltantes)")

        # Agrupamos por Artículo para ver su comportamiento en la cadena
        resumen_sku = df_analisis.groupby(['Articulo', 'Familia']).agg(
            Tiendas_de_Alta=('Tienda', 'count'),
            Tiendas_con_Stock=('Con Stock', 'sum')
        ).reset_index()

        resumen_sku['Tiendas_sin_Stock'] = resumen_sku['Tiendas_de_Alta'] - resumen_sku['Tiendas_con_Stock']
        resumen_sku = resumen_sku.sort_values('Tiendas_sin_Stock', ascending=False)

        st.write("Esta tabla responde: ¿En cuántas tiendas falta este código específico?")
        st.dataframe(resumen_sku.head(100), hide_index=True, use_container_width=True)

        # --- SECCIÓN 3: ¿EN DÓNDE? ---
        st.markdown("---")
        st.subheader("📍 3. ¿En qué Zonas/Regiones hay más faltantes?")

        resumen_zona = df_analisis.groupby('Zona').agg(
            Alta_Total=('Articulo', 'count'),
            Con_Stock=('Con Stock', 'sum')
        ).reset_index()
        resumen_zona['Faltantes'] = resumen_zona['Alta_Total'] - resumen_zona['Con_Stock']
        resumen_zona['Cobertura (%)'] = (resumen_zona['Con_Stock'] / resumen_zona['Alta_Total'] * 100).round(1)

        st.dataframe(resumen_zona.sort_values('Cobertura (%)'), hide_index=True, use_container_width=True)

    # BUSCADOR INDIVIDUAL
    st.markdown("---")
    st.subheader("🔎 Detalle de Faltantes por Familia")
    fam_sel = st.selectbox("Selecciona Familia:", resumen_familia['Familia'].unique())
    det = df_analisis[(df_analisis['Familia'] == fam_sel) & (df_analisis['Con Stock'] == False)]
    st.dataframe(det[['Tienda', 'Zona', 'Articulo', 'Sector', 'Amplitud']], hide_index=True, use_container_width=True)

else:
    st.info("Carga el archivo 'tiendas.xlsx' para comenzar.")
import streamlit as st
import pandas as pd
import os
import io

# Configuración de la página
st.set_page_config(page_title="Dashboard de Cobertura de Stock", layout="wide")
st.title("📦 Análisis de Cobertura y Faltantes de Stock")

@st.cache_data(show_spinner=False)
def cargar_datos():
    try:
        st.write("📥 Cargando tiendas.xlsx...")
        df_tiendas_zona = pd.read_excel('tiendas.xlsx')
        df_tiendas_zona.columns = ['Tienda', 'Zona']
        lista_tiendas_permitidas = df_tiendas_zona['Tienda'].unique()
        st.success(f"✅ tiendas.xlsx cargado | {len(df_tiendas_zona)} registros")

        # 1. Cargar Sectores Tienda
        st.write("📥 Cargando SectoresTienda.xlsx...")
        df_sec_tienda = pd.read_excel('SectoresTienda.xlsx')
        df_sec_tienda.columns = df_sec_tienda.columns.str.strip()
        df_sec_tienda.rename(columns=lambda x: x.lower(), inplace=True)
        df_sec_tienda.rename(columns={
            'tienda': 'Tienda',
            'sector tienda': 'Sector',
            'amplitud tienda': 'Amplitud'
        }, inplace=True)

        df_sec_tienda = df_sec_tienda[df_sec_tienda['Tienda'].isin(lista_tiendas_permitidas)]
        st.success(f"✅ SectoresTienda.xlsx cargado | {len(df_sec_tienda)} registros")

        # 1.5 Cargar Sectores Articulos
        st.write("📥 Cargando SectoresArticulos.xlsx...")
        df_sec_art = pd.read_excel('SectoresArticulos.xlsx')
        df_sec_art.columns = df_sec_art.columns.str.strip()
        df_sec_art.rename(columns=lambda x: x.title(), inplace=True)
        st.success(f"✅ SectoresArticulos.xlsx cargado | {len(df_sec_art)} registros")

        # Cruzar para obtener el Alta
        st.write("🔄 Generando cruce de alta...")
        df_alta = pd.merge(
            df_sec_tienda,
            df_sec_art,
            on=['Sector', 'Amplitud'],
            how='inner'
        )
        st.success(f"✅ Cruce generado | {len(df_alta)} registros")

        # 2. Cargar Familias
        st.write("📥 Cargando Familias.xlsx...")
        df_familias = pd.read_excel('Familias.xlsx')
        df_familias = df_familias.iloc[:, :3]
        df_familias.columns = ['Articulo', 'Familia', 'Descripcion']

        df_alta = pd.merge(df_alta, df_familias, on='Articulo', how='left')
        df_alta['Familia'] = df_alta['Familia'].fillna('SIN FAMILIA')
        df_alta['Descripcion'] = df_alta['Descripcion'].fillna('SIN DESCRIPCION')

        st.success(f"✅ Familias cargadas | {len(df_familias)} registros")

        # 3. Cargar los CSV de Stock
        st.write("📥 Cargando bases de stock...")
        bases_stock = []

        for i in range(1, 5):
            archivo = f'base{i}.csv'

            if os.path.exists(archivo):
                st.write(f"📄 Procesando {archivo}...")

                try:
                    df_base = pd.read_csv(
                        archivo,
                        sep=None,
                        engine='python',
                        encoding='utf-8-sig'
                    )
                except:
                    df_base = pd.read_csv(
                        archivo,
                        sep=None,
                        engine='python'
                    )

                st.write(f"✅ {archivo} cargado | {len(df_base)} registros")

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
                    df_base = df_base[
                        df_base['Tienda'].isin(lista_tiendas_permitidas)
                    ]

                    bases_stock.append(df_base[columnas_necesarias])

                    st.success(f"✅ {archivo} agregado al consolidado")

                else:
                    st.error(f"❌ {archivo} no tiene columnas necesarias")

            else:
                st.warning(f"⚠️ No existe {archivo}")

        if bases_stock:
            st.write("🔄 Consolidando stock...")

            df_stock = pd.concat(bases_stock, ignore_index=True)

            for col in ['Tienda', 'Articulo']:
                df_stock[col] = pd.to_numeric(df_stock[col], errors='coerce')
                df_alta[col] = pd.to_numeric(df_alta[col], errors='coerce')

            df_stock = df_stock.groupby(
                ['Tienda', 'Articulo'],
                as_index=False
            )['Stock Cet'].sum()

            st.success(f"✅ Stock consolidado | {len(df_stock)} registros")

            return df_alta, df_stock, df_tiendas_zona

        else:
            st.error("❌ No se cargó ninguna base de stock")

            return (
                df_alta,
                pd.DataFrame(columns=['Tienda', 'Articulo', 'Stock Cet']),
                df_tiendas_zona
            )

    except Exception as e:
        st.error(f"❌ Error crítico: {e}")

        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()


def generar_excel(df_resumen):
    output = io.BytesIO()

    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_resumen.to_excel(
            writer,
            index=False,
            sheet_name='Resumen'
        )

        workbook = writer.book

        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#D7E4BC',
            'border': 1
        })

        worksheet = writer.sheets['Resumen']

        for col_num, value in enumerate(df_resumen.columns.values):
            worksheet.write(0, col_num, value, header_format)
            worksheet.set_column(col_num, col_num, 20)

    return output.getvalue()


# --- EJECUCIÓN ---
st.write("🚀 Iniciando carga de datos...")

df_alta_total, df_stock_total, df_zonas = cargar_datos()

st.success("✅ Proceso de carga finalizado")

if not df_alta_total.empty:

    tiendas_disponibles = sorted(
        df_alta_total['Tienda'].dropna().unique()
    )

    opciones_selector = ["Todas las tiendas"] + [
        int(t) for t in tiendas_disponibles
    ]

    tienda_seleccionada = st.selectbox(
        "Selecciona una Tienda",
        opciones_selector
    )

    st.markdown("---")

    if tienda_seleccionada == "Todas las tiendas":
        alta_tienda = df_alta_total.copy()
        stock_tienda = df_stock_total.copy()

    else:
        alta_tienda = df_alta_total[
            df_alta_total['Tienda'] == tienda_seleccionada
        ].copy()

        stock_tienda = df_stock_total[
            df_stock_total['Tienda'] == tienda_seleccionada
        ].copy()

    st.write("🔄 Generando análisis...")

    df_analisis = pd.merge(
        alta_tienda,
        stock_tienda[['Tienda', 'Articulo', 'Stock Cet']],
        on=['Tienda', 'Articulo'],
        how='left'
    )

    df_analisis['Stock Cet'] = pd.to_numeric(
        df_analisis['Stock Cet'],
        errors='coerce'
    ).fillna(0)

    df_analisis['Con Stock'] = df_analisis['Stock Cet'] > 0

    df_analisis = pd.merge(
        df_analisis,
        df_zonas,
        on='Tienda',
        how='left'
    )

    st.success(f"✅ Análisis generado | {len(df_analisis)} registros")

    # KPIs
    total_articulos_alta = len(df_analisis)
    articulos_con_stock = df_analisis['Con Stock'].sum()
    articulos_faltantes = total_articulos_alta - articulos_con_stock

    cobertura_pct = (
        articulos_con_stock / total_articulos_alta * 100
    ) if total_articulos_alta > 0 else 0

    st.subheader(f"Resumen Operativo: {tienda_seleccionada}")

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Impactos de Alta", f"{total_articulos_alta:,}")
    col2.metric("Impactos con Stock", f"{articulos_con_stock:,}")
    col3.metric("Cobertura (%)", f"{cobertura_pct:.1f} %")
    col4.metric("Huecos Totales", f"{articulos_faltantes:,}")

else:
    st.error("❌ No se pudieron cargar los datos")
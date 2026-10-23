
import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

# --------------------------------------------------
# CONFIGURACIÓN
# --------------------------------------------------

st.set_page_config(
    page_title="Minimarket Altez",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded"
)

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "datos_demo" / "ALTES_DEMO.db"

# Estilos visuales
st.markdown("""
<style>
    .stApp {
        background-color: #080d1c;
        color: #f3f4f6;
    }

    [data-testid="stSidebar"] {
        background-color: #10182a;
    }

    [data-testid="stMetric"] {
        background-color: #111a2d;
        padding: 18px;
        border: 1px solid #253149;
        border-radius: 14px;
    }

    [data-testid="stMetricLabel"] {
        color: #9db2d0;
    }

    [data-testid="stMetricValue"] {
        color: #38d9a9;
    }

    h1, h2, h3 {
        color: #f8fafc;
    }
</style>
""", unsafe_allow_html=True)


# --------------------------------------------------
# CONEXIÓN CON SQLITE
# --------------------------------------------------

def consultar_sql(consulta, parametros=()):
    """Ejecuta consultas de lectura en SQLite."""
    with sqlite3.connect(DB_PATH, timeout=10) as conexion:
        conexion.execute("PRAGMA query_only = ON")
        return pd.read_sql_query(
            consulta,
            conexion,
            params=parametros
        )


if not DB_PATH.exists():
    st.error(f"No se encontró la base de datos: {DB_PATH}")
    st.stop()


# --------------------------------------------------
# CONSULTAS E INDICADORES
# --------------------------------------------------

try:
    productos = consultar_sql("""
        SELECT
            p.producto_id,
            p.nombre,
            p.precio_compra,
            p.precio_venta,
            p.estado,
            c.nombre AS categoria,
            COALESCE(i.stock_actual, 0) AS stock_actual,
            COALESCE(i.stock_minimo, 0) AS stock_minimo
        FROM Producto p
        LEFT JOIN Categoria c
            ON p.categoria_id = c.categoria_id
        LEFT JOIN Inventario i
            ON p.producto_id = i.producto_id
    """)

    ventas = consultar_sql("""
        SELECT
            venta_id,
            fecha_venta,
            subtotal,
            igv,
            total,
            estado
        FROM Venta
        ORDER BY fecha_venta DESC
    """)

    detalle = consultar_sql("""
        SELECT
            dv.producto_id,
            p.nombre AS producto,
            SUM(dv.cantidad) AS unidades_vendidas,
            SUM(dv.subtotal) AS importe_vendido
        FROM Detalle_Venta dv
        JOIN Venta v
            ON dv.venta_id = v.venta_id
        JOIN Producto p
            ON dv.producto_id = p.producto_id
        WHERE v.estado = 1
        GROUP BY dv.producto_id, p.nombre
        ORDER BY unidades_vendidas DESC
    """)

    lotes = consultar_sql("""
        SELECT
            l.numero_lote,
            p.nombre AS producto,
            l.cantidad,
            l.fecha_vencimiento
        FROM Lote l
        JOIN Producto p
            ON l.producto_id = p.producto_id
        WHERE l.estado = 1
          AND l.fecha_vencimiento IS NOT NULL
        ORDER BY l.fecha_vencimiento
    """)

except Exception as error:
    st.error(f"No se pudieron consultar los datos: {error}")
    st.stop()


# --------------------------------------------------
# MENÚ LATERAL
# --------------------------------------------------

st.sidebar.title("🛒 Minimarket Altez")
st.sidebar.caption("Sistema de gestión")

pagina = st.sidebar.radio(
    "Navegación",
    [
        "Resumen",
        "Productos",
        "Inventario",
        "Ventas",
        "Vencimientos"
    ]
)

st.sidebar.divider()
st.sidebar.caption("Base de datos: ALTES_BD.db")


# --------------------------------------------------
# RESUMEN
# --------------------------------------------------

if pagina == "Resumen":

    st.title("Resumen y métricas")
    st.caption("Panel general del minimarket")

    productos_activos = productos[
        productos["estado"] == 1
    ]

    ventas_validas = ventas[
        ventas["estado"] == 1
    ]

    valor_inventario = (
        productos_activos["stock_actual"]
        * productos_activos["precio_venta"]
    ).sum()

    total_ventas = ventas_validas["total"].sum()

    stock_critico = productos_activos[
        productos_activos["stock_actual"]
        <= productos_activos["stock_minimo"]
    ]

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Productos activos",
        len(productos_activos)
    )

    c2.metric(
        "Valor del inventario",
        f"S/ {valor_inventario:,.2f}"
    )

    c3.metric(
        "Ventas registradas",
        f"S/ {total_ventas:,.2f}"
    )

    c4.metric(
        "Stock crítico",
        len(stock_critico)
    )

    st.divider()

    izquierda, derecha = st.columns(2)

    with izquierda:
        st.subheader("Productos más vendidos")

        if detalle.empty:
            st.info("Todavía no hay ventas registradas.")
        else:
            top = detalle.head(5)

            figura = px.bar(
                top.sort_values("unidades_vendidas"),
                x="unidades_vendidas",
                y="producto",
                orientation="h",
                labels={
                    "unidades_vendidas": "Unidades",
                    "producto": "Producto"
                }
            )

            figura.update_layout(
                template="plotly_dark",
                paper_bgcolor="#111a2d",
                plot_bgcolor="#111a2d"
            )

            st.plotly_chart(
                figura,
                use_container_width=True
            )

    with derecha:
        st.subheader("Inventario por categoría")

        distribucion = (
            productos_activos
            .groupby("categoria", dropna=False)["stock_actual"]
            .sum()
            .reset_index()
        )

        distribucion["categoria"] = (
            distribucion["categoria"].fillna("Sin categoría")
        )

        if distribucion.empty:
            st.info("No hay inventario disponible.")
        else:
            figura = px.pie(
                distribucion,
                names="categoria",
                values="stock_actual",
                hole=0.55
            )

            figura.update_layout(
                template="plotly_dark",
                paper_bgcolor="#111a2d"
            )

            st.plotly_chart(
                figura,
                use_container_width=True
            )

    st.subheader("Últimas ventas")

    if ventas_validas.empty:
        st.info("No hay ventas registradas.")
    else:
        st.dataframe(
            ventas_validas[
                ["venta_id", "fecha_venta", "total"]
            ].head(10),
            use_container_width=True,
            hide_index=True
        )

    st.subheader("Productos que necesitan revisión")

    if stock_critico.empty:
        st.success("No se detectan productos con stock crítico.")
    else:
        st.dataframe(
            stock_critico[
                [
                    "nombre",
                    "categoria",
                    "stock_actual",
                    "stock_minimo"
                ]
            ],
            use_container_width=True,
            hide_index=True
        )


# --------------------------------------------------
# PRODUCTOS
# --------------------------------------------------

elif pagina == "Productos":

    st.title("Catálogo de productos")

    busqueda = st.text_input("Buscar producto")

    filtrados = productos.copy()

    if busqueda:
        filtrados = filtrados[
            filtrados["nombre"].str.contains(
                busqueda,
                case=False,
                na=False
            )
        ]

    st.dataframe(
        filtrados,
        use_container_width=True,
        hide_index=True
    )


# --------------------------------------------------
# INVENTARIO
# --------------------------------------------------

elif pagina == "Inventario":

    st.title("Control de inventario")

    st.dataframe(
        productos[
            [
                "nombre",
                "categoria",
                "stock_actual",
                "stock_minimo",
                "precio_compra",
                "precio_venta"
            ]
        ].sort_values("nombre"),
        use_container_width=True,
        hide_index=True
    )

    st.caption(
        "El valor del inventario se calcula al precio de venta. "
        "Puedes cambiarlo para analizar el costo de adquisición."
    )


# --------------------------------------------------
# VENTAS
# --------------------------------------------------

elif pagina == "Ventas":

    st.title("Historial de ventas")

    if not ventas.empty:
        st.dataframe(
            ventas,
            use_container_width=True,
            hide_index=True
        )

        st.subheader("Detalle de productos vendidos")

        st.dataframe(
            detalle,
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No hay ventas registradas.")


# --------------------------------------------------
# VENCIMIENTOS
# --------------------------------------------------

elif pagina == "Vencimientos":

    st.title("Control de vencimientos")

    if lotes.empty:
        st.info("No hay lotes con fecha de vencimiento registrada.")
    else:
        lotes["fecha_vencimiento"] = pd.to_datetime(
            lotes["fecha_vencimiento"],
            errors="coerce"
        )

        hoy = pd.Timestamp.today().normalize()

        lotes["dias_para_vencer"] = (
            lotes["fecha_vencimiento"] - hoy
        ).dt.days

        proximos = lotes[
            lotes["dias_para_vencer"].notna()
            & (lotes["dias_para_vencer"] <= 30)
        ]

        st.subheader("Lotes que vencen en 30 días o menos")

        st.dataframe(
            proximos,
            use_container_width=True,
            hide_index=True
        )

        st.subheader("Todos los lotes")

        st.dataframe(
            lotes,
            use_container_width=True,
            hide_index=True
        )
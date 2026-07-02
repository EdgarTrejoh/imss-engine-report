import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

CSV_PATH = r"C:\Users\IN335265\OneDrive - INFONAVIT\Documents\Otros\Traslate\Entregas\001_pruebas\005_exports\gpt_projects\reporte_economico_2026_IA\005_etl\03_imss\imss_analisis_profundo_concentrado.csv"  # <-- cambia esto

# ---------- utilidades ----------
def nice_theme(fig, title):
    fig.update_layout(
        title=title,
        hovermode="x unified",
        legend_title_text="",
        margin=dict(l=60, r=20, t=70, b=60),
        font=dict(size=14),
    )
    fig.update_xaxes(title="Periodo")
    return fig

# ---------- query base (agregación ligera) ----------
con = duckdb.connect(database=":memory:")
con.execute("PRAGMA threads=4;")  # ajusta si quieres

# 1) Serie por sexo (asegurados, masa, salario prom)
df_sexo = con.execute(f"""
WITH base AS (
  SELECT
    periodo_informacion::DATE AS periodo,
    sexo,
    SUM(total_asegurados)    AS asegurados,
    SUM(masa_salarial_total) AS masa
  FROM read_csv_auto('{CSV_PATH.replace("\\", "/")}', sample_size=200000, ignore_errors=true)
  GROUP BY 1,2
)
SELECT
  periodo,
  sexo,
  asegurados,
  masa,
  CASE WHEN asegurados=0 THEN NULL ELSE masa/asegurados END AS salario_prom
FROM base
ORDER BY periodo, sexo;
""").df()

# 2) Último periodo (snapshot) por entidad y sexo
df_last_ent = con.execute(f"""
WITH base AS (
  SELECT
    periodo_informacion::DATE AS periodo,
    cve_entidad,
    sexo,
    SUM(total_asegurados) AS asegurados
  FROM read_csv_auto('{CSV_PATH.replace("\\", "/")}', sample_size=200000, ignore_errors=true)
  GROUP BY 1,2,3
),
lastp AS (SELECT MAX(periodo) AS periodo FROM base)
SELECT b.*
FROM base b
JOIN lastp l USING(periodo);
""").df()

# 3) Serie nacional para shock COVID (asegurados total)
df_nat = con.execute(f"""
SELECT
  periodo_informacion::DATE AS periodo,
  SUM(total_asegurados) AS asegurados
FROM read_csv_auto('{CSV_PATH.replace("\\", "/")}', sample_size=200000, ignore_errors=true)
GROUP BY 1
ORDER BY 1;
""").df()

# 4) Participación por sexo (share)
df_share = con.execute(f"""
WITH base AS (
  SELECT
    periodo_informacion::DATE AS periodo,
    sexo,
    SUM(total_asegurados) AS asegurados
  FROM read_csv_auto('{CSV_PATH.replace("\\", "/")}', sample_size=200000, ignore_errors=true)
  GROUP BY 1,2
),
tot AS (
  SELECT periodo, SUM(asegurados) AS total
  FROM base GROUP BY 1
)
SELECT
  b.periodo, b.sexo, b.asegurados,
  (b.asegurados / NULLIF(t.total,0)) * 100 AS share_pct
FROM base b
JOIN tot t USING(periodo)
ORDER BY periodo, sexo;
""").df()

# 5) Top sectores por salario promedio (último periodo) + sexo
df_sector_last = con.execute(f"""
WITH base AS (
  SELECT
    periodo_informacion::DATE AS periodo,
    sector_economico_1 AS sector,
    sexo,
    SUM(total_asegurados) AS asegurados,
    SUM(masa_salarial_total) AS masa
  FROM read_csv_auto('{CSV_PATH.replace("\\", "/")}', sample_size=200000, ignore_errors=true)
  GROUP BY 1,2,3
),
lastp AS (SELECT MAX(periodo) AS periodo FROM base),
snap AS (
  SELECT *
  FROM base
  JOIN lastp USING(periodo)
)
SELECT
  periodo, sector, sexo,
  asegurados,
  CASE WHEN asegurados=0 THEN NULL ELSE masa/asegurados END AS salario_prom
FROM snap
WHERE asegurados > 0;
""").df()

con.close()

# ---------- (GRÁFICA 1) Asegurados por sexo ----------
fig1 = px.line(df_sexo, x="periodo", y="asegurados", color="sexo",
               title="IMSS — Asegurados por sexo (Nacional)")
nice_theme(fig1, "IMSS — Asegurados por sexo (Nacional)")
fig1.show()

# ---------- (GRÁFICA 2) Salario promedio por sexo ----------
fig2 = px.line(df_sexo, x="periodo", y="salario_prom", color="sexo",
               title="IMSS — Salario promedio estimado (masa/asegurados) por sexo")
nice_theme(fig2, "IMSS — Salario promedio estimado por sexo (masa / asegurados)")
fig2.update_yaxes(title="Salario promedio (estimado)")
fig2.show()

# ---------- (GRÁFICA 3) Participación % por sexo (stack area) ----------
fig3 = px.area(df_share, x="periodo", y="share_pct", color="sexo",
               title="IMSS — Participación (%) de asegurados por sexo",
               groupnorm="")  # ya viene en %
nice_theme(fig3, "IMSS — Participación (%) de asegurados por sexo")
fig3.update_yaxes(title="Participación (%)", rangemode="tozero")
fig3.show()

# ---------- (GRÁFICA 4) Shock (variación anual %) del total nacional ----------
df_nat["yoy_pct"] = df_nat["asegurados"].pct_change(12) * 100
fig4 = px.line(df_nat, x="periodo", y="yoy_pct",
               title="IMSS — Variación anual (%) de asegurados (Nacional)")
nice_theme(fig4, "IMSS — Variación anual (%) de asegurados (Nacional)")
fig4.update_yaxes(title="YoY %", zeroline=True)
fig4.show()

# ---------- (GRÁFICA 5) Ranking por estado en el último periodo (top 15) ----------
# Top 15 estados por total (sumando sexos) y apilado por sexo
top_states = (
    df_last_ent.groupby("cve_entidad", as_index=False)["asegurados"].sum()
    .sort_values("asegurados", ascending=False)
    .head(15)["cve_entidad"]
)
df_top_states = df_last_ent[df_last_ent["cve_entidad"].isin(top_states)].copy()
df_top_states["cve_entidad"] = df_top_states["cve_entidad"].astype(str)

fig5 = px.bar(
    df_top_states,
    x="cve_entidad",
    y="asegurados",
    color="sexo",
    title=f"IMSS — Top 15 entidades por asegurados (último periodo = {df_top_states['periodo'].iloc[0]})",
    barmode="stack",
)
nice_theme(fig5, f"IMSS — Top 15 entidades por asegurados (último periodo)")
fig5.update_xaxes(title="Entidad (cve_entidad)")
fig5.update_yaxes(title="Asegurados")
fig5.show()

# ---------- BONUS: Top sectores por salario (último periodo) ----------
# (si quieres que sea una 6ta gráfica, descomenta)
# df_top_sector = (df_sector_last.groupby(["sector","sexo"], as_index=False)
#                  .agg({"asegurados":"sum","salario_prom":"mean"}))
# df_top_sector = df_top_sector.sort_values("salario_prom", ascending=False).head(20)
# fig6 = px.bar(df_top_sector, x="salario_prom", y="sector", color="sexo", orientation="h",
#               title="IMSS — Top sectores por salario promedio (último periodo)")
# nice_theme(fig6, "IMSS — Top sectores por salario promedio (último periodo)")
# fig6.show()

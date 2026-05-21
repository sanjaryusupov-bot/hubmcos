import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from io import BytesIO
import random
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os

# ---------------- SETTINGS ----------------

st.set_page_config(
    page_title="Отгрузка маршрутов",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    .stMetric { background-color: #f0f2f6; padding: 15px; border-radius: 10px; text-align: center; }
    .stButton button { background-color: #4CAF50; color: white; font-weight: bold; font-size: 16px; padding: 10px 20px; border-radius: 8px; width: 100%; }
    .stButton button:hover { background-color: #45a049; }
    </style>
""", unsafe_allow_html=True)

SHEET_ID = "1hKZ8ggNLW-OY1bV8xAW7PKl50Fof2co86oxGK92YPAA"
SHEET_NAME = "Маршруты"

# ---------------- GOOGLE SHEETS ----------------

def connect_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID).worksheet(SHEET_NAME)

def get_data():
    sheet = connect_sheet()
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    
    required_columns = ["Статус отгрузки", "Дата отгрузки факт", "Номер машины", "Водитель", "№ пломбы"]
    for col in required_columns:
        if col not in df.columns:
            df[col] = ""
    
    if "кол-во штук в заказе" in df.columns:
        df["кол-во штук в заказе"] = pd.to_numeric(df["кол-во штук в заказе"], errors='coerce').fillna(0)
    
    return df

def update_route(route_name, car_number, driver, plomb):
    sheet = connect_sheet()
    data = sheet.get_all_records()
    headers = sheet.row_values(1)
    
    extra_columns = ["Номер машины", "Водитель", "№ пломбы"]
    for col_name in extra_columns:
        if col_name not in headers:
            sheet.update_cell(1, len(headers) + 1, col_name)
            headers.append(col_name)
    
    status_col = headers.index("Статус отгрузки") + 1
    fact_col = headers.index("Дата отгрузки факт") + 1
    car_col = headers.index("Номер машины") + 1
    driver_col = headers.index("Водитель") + 1
    plomb_col = headers.index("№ пломбы") + 1
    
    for idx, row in enumerate(data, start=2):
        if str(row.get("Номер маршрута", "")) == str(route_name):
            sheet.update_cell(idx, status_col, "ОТГРУЖЕН")
            sheet.update_cell(idx, fact_col, datetime.now().strftime("%d.%m.%Y %H:%M"))
            sheet.update_cell(idx, car_col, car_number)
            sheet.update_cell(idx, driver_col, driver)
            sheet.update_cell(idx, plomb_col, plomb)
            break

# ---------------- PDF GENERATION ----------------

# Создаем простой PDF без сложных шрифтов, используя стандартные
def generate_pdf(all_routes_df, routes_list, driver, car, plomb):
    buffer = BytesIO()
    
    # Создаем PDF
    c = canvas.Canvas(buffer, pagesize=landscape(A4))
    width, height = landscape(A4)  # 297 x 210
    
    # Используем стандартный шрифт Helvetica
    c.setFont("Helvetica", 10)
    
    y = height - 30
    x = 20
    
    # Заголовок
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width/2, y, "MARSHRUTNIY LIST")
    y -= 15
    
    # Номер
    c.setFont("Helvetica", 10)
    c.drawString(x, y, f"Nomer: {random.randint(10000, 99999)}")
    y -= 12
    
    # Информация
    c.drawString(x, y, f"Voditel: {driver}")
    y -= 10
    c.drawString(x, y, f"Avto: {car}")
    y -= 10
    c.drawString(x, y, f"Data: {datetime.now().strftime('%d.%m.%Y')}")
    y -= 10
    c.drawString(x, y, f"Plomba: {plomb}")
    y -= 15
    
    # Маршруты
    c.setFont("Helvetica-Bold", 10)
    c.drawString(x, y, "Marshruti v reyse:")
    y -= 8
    c.setFont("Helvetica", 9)
    for route in routes_list:
        route_data = all_routes_df[all_routes_df["Номер маршрута"] == route]
        c.drawString(x + 5, y, f"- Marshrut {route} ({len(route_data)} magaz., {int(route_data['кол-во штук в заказе'].sum())} korobok)")
        y -= 8
    y -= 8
    
    # Коробки
    c.setFont("Helvetica-Bold", 10)
    c.drawString(x, y, f"Voditel {driver} poluchil vsego __________ korobov dlya {len(all_routes_df)} magazinov")
    y -= 20
    
    # Таблица
    headers = ["#", "Zakaz", "Magazin", "Adres", "Marshrut", "Plomba", "Vydano", "Polucheno", "Podpis", "Podpis vod"]
    col_widths = [8, 18, 30, 40, 15, 15, 15, 15, 20, 20]
    
    # Рисуем заголовки
    c.setFont("Helvetica-Bold", 7)
    x_pos = x
    for i, h in enumerate(headers):
        c.rect(x_pos, y - 10, col_widths[i], 10, fill=0)
        c.drawCentredString(x_pos + col_widths[i]/2, y - 5, h)
        x_pos += col_widths[i]
    
    y -= 10
    c.setFont("Helvetica", 6)
    
    # Данные
    for idx, (_, row) in enumerate(all_routes_df.iterrows(), start=1):
        x_pos = x
        if y < 50:
            c.showPage()
            y = height - 30
            c.setFont("Helvetica-Bold", 7)
            x_pos = x
            for i, h in enumerate(headers):
                c.rect(x_pos, y - 10, col_widths[i], 10, fill=0)
                c.drawCentredString(x_pos + col_widths[i]/2, y - 5, h)
                x_pos += col_widths[i]
            y -= 10
            c.setFont("Helvetica", 6)
            x_pos = x
        
        c.rect(x_pos, y - 8, col_widths[0], 8)
        c.drawCentredString(x_pos + col_widths[0]/2, y - 4, str(idx))
        x_pos += col_widths[0]
        
        c.rect(x_pos, y - 8, col_widths[1], 8)
        c.drawCentredString(x_pos + col_widths[1]/2, y - 4, str(row.get("№ заказа", ""))[:10])
        x_pos += col_widths[1]
        
        c.rect(x_pos, y - 8, col_widths[2], 8)
        c.drawString(x_pos + 2, y - 4, str(row.get("Название магазина", ""))[:20])
        x_pos += col_widths[2]
        
        c.rect(x_pos, y - 8, col_widths[3], 8)
        c.drawString(x_pos + 2, y - 4, str(row.get("Адрес магазина", ""))[:30])
        x_pos += col_widths[3]
        
        c.rect(x_pos, y - 8, col_widths[4], 8)
        c.drawCentredString(x_pos + col_widths[4]/2, y - 4, str(row.get("Номер маршрута", "")))
        x_pos += col_widths[4]
        
        c.rect(x_pos, y - 8, col_widths[5], 8)
        c.drawCentredString(x_pos + col_widths[5]/2, y - 4, plomb[:8])
        x_pos += col_widths[5]
        
        c.rect(x_pos, y - 8, col_widths[6], 8)
        c.drawCentredString(x_pos + col_widths[6]/2, y - 4, str(int(row.get("кол-во штук в заказе", 0))))
        x_pos += col_widths[6]
        
        c.rect(x_pos, y - 8, col_widths[7], 8)
        c.drawCentredString(x_pos + col_widths[7]/2, y - 4, "_____")
        x_pos += col_widths[7]
        
        c.rect(x_pos, y - 8, col_widths[8], 8)
        c.drawCentredString(x_pos + col_widths[8]/2, y - 4, "______")
        x_pos += col_widths[8]
        
        c.rect(x_pos, y - 8, col_widths[9], 8)
        c.drawCentredString(x_pos + col_widths[9]/2, y - 4, "______")
        
        y -= 10
    
    y -= 15
    
    # Итого
    c.setFont("Helvetica-Bold", 10)
    c.drawString(x, y, f"ITOGO korobov: {int(all_routes_df['кол-во штук в заказе'].sum())}")
    y -= 20
    
    # Подписи
    c.setFont("Helvetica", 9)
    c.drawString(x, y, "Podpis voditelya: ___________________________")
    y -= 10
    c.drawString(x, y, "Podpis prinimayuschey storony: ___________________________")
    y -= 10
    c.drawString(x, y, "Pechat: ___________________________")
    
    c.save()
    buffer.seek(0)
    return buffer

# ---------------- UI ----------------

st.title("🚚 Sistema upravleniya otgruzkoy marshrutov")
st.markdown("---")

try:
    df = get_data()
except Exception as e:
    st.error(f"Error: {str(e)}")
    st.stop()

if "Статус отгрузки" in df.columns:
    not_shipped = df[df["Статус отгрузки"] != "ОТГРУЖЕН"]
    shipped = df[df["Статус отгрузки"] == "ОТГРУЖЕН"]
else:
    not_shipped = df.copy()
    shipped = pd.DataFrame()

# METRICS
col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.metric("Ne otgruzheno", not_shipped["Номер маршрута"].nunique() if len(not_shipped) > 0 else 0)
with col2:
    st.metric("Otgruzheno", shipped["Номер маршрута"].nunique() if len(shipped) > 0 else 0)
with col3:
    st.metric("Tochek", len(not_shipped))
with col4:
    total_boxes = not_shipped["кол-во штук в заказе"].sum() if len(not_shipped) > 0 else 0
    st.metric("Korobok", int(total_boxes))
with col5:
    completion = (shipped["Номер маршрута"].nunique() / df["Номер маршрута"].nunique() * 100) if len(df) > 0 else 0
    st.metric("Progress", f"{completion:.1f}%")

st.markdown("---")

# SIDEBAR
with st.sidebar:
    st.header("Detali")
    view_type = st.radio("Pokazat:", ["Neotgruzhennye", "Otgruzhennye", "Vse"])
    
    if view_type == "Neotgruzhennye":
        display_df = not_shipped
    elif view_type == "Otgruzhennye":
        display_df = shipped
    else:
        display_df = df
    
    if len(display_df) > 0:
        route_summary = display_df.groupby("Номер маршрута").agg({
            "№ заказа": "count",
            "кол-во штук в заказе": "sum"
        }).rename(columns={"№ заказа": "Zakazov", "кол-во штук в заказе": "Korobok"})
        st.dataframe(route_summary, use_container_width=True)

st.markdown("---")

# FORM
st.subheader("Otgruzka marshrutov")

col1, col2, col3 = st.columns(3)
with col1:
    car_number = st.text_input("Nomer mashiny", placeholder="A123BC77")
with col2:
    driver = st.text_input("Voditel", placeholder="Ivanov I.I.")
with col3:
    plomb = st.text_input("Nomer plomby", placeholder="12345")

st.markdown("---")

not_shipped_routes = sorted(not_shipped["Номер маршрута"].dropna().unique()) if len(not_shipped) > 0 else []

if len(not_shipped_routes) > 0:
    st.subheader("Vyberite marshruty")
    selected_routes = st.multiselect("Marshruty:", options=not_shipped_routes)
    
    if selected_routes:
        details_df = not_shipped[not_shipped["Номер маршрута"].isin(selected_routes)]
        st.info(f"Vybranno: {len(selected_routes)} marshrutov | {len(details_df)} magazinov | {int(details_df['кол-во штук в заказе'].sum())} korobok")
        
        if st.button("OTGRUZIT", type="primary", use_container_width=True):
            if not car_number:
                st.error("Vvedite nomer mashiny!")
                st.stop()
            if not driver:
                st.error("Vvedite voditelya!")
                st.stop()
            
            selected_data = df[df["Номер маршрута"].isin(selected_routes)]
            
            progress = st.progress(0)
            for i, route in enumerate(selected_routes):
                update_route(route, car_number, driver, plomb)
                progress.progress((i + 1) / len(selected_routes))
            
            pdf_buffer = generate_pdf(selected_data, selected_routes, driver, car_number, plomb)
            
            st.success(f"Otgruzheno {len(selected_routes)} marshrutov!")
            
            st.download_button(
                label="Skachat PDF",
                data=pdf_buffer,
                file_name=f"marshrut_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                mime="application/pdf"
            )
else:
    st.info("Vse marshruty otgruzheny!")

st.caption(f"Obnovleno: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")

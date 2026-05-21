import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from io import BytesIO
import random
from fpdf import FPDF
import urllib.request
import os

# ---------------- SETTINGS ----------------

st.set_page_config(
    page_title="Отгрузка маршрутов",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Применяем пользовательский CSS
st.markdown("""
    <style>
    .stMetric {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
    }
    .stButton button {
        background-color: #4CAF50;
        color: white;
        font-weight: bold;
        font-size: 16px;
        padding: 10px 20px;
        border-radius: 8px;
        border: none;
        width: 100%;
    }
    .stButton button:hover {
        background-color: #45a049;
    }
    </style>
""", unsafe_allow_html=True)

SHEET_ID = "1hKZ8ggNLW-OY1bV8xAW7PKl50Fof2co86oxGK92YPAA"
SHEET_NAME = "Маршруты"

# ---------------- GOOGLE SHEETS ----------------

def connect_sheet():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]

    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        st.secrets["gcp_service_account"],
        scope
    )

    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID).worksheet(SHEET_NAME)
    return sheet

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
    current_headers = headers.copy()
    
    for col_name in extra_columns:
        if col_name not in current_headers:
            sheet.update_cell(1, len(current_headers) + 1, col_name)
            current_headers.append(col_name)
    
    headers = sheet.row_values(1)
    
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

# ---------------- PDF GENERATION WITH FPDF ----------------

def download_dejavu_fonts():
    """Скачивает шрифты DejaVu для поддержки русского языка"""
    fonts = {
        '/tmp/DejaVuSans.ttf': 'https://github.com/dejavu-fonts/dejavu-fonts/raw/master/ttf/DejaVuSans.ttf',
        '/tmp/DejaVuSans-Bold.ttf': 'https://github.com/dejavu-fonts/dejavu-fonts/raw/master/ttf/DejaVuSans-Bold.ttf'
    }
    
    for path, url in fonts.items():
        if not os.path.exists(path):
            try:
                urllib.request.urlretrieve(url, path)
            except Exception as e:
                print(f"Ошибка скачивания шрифта: {e}")

class RussianPDF(FPDF):
    def __init__(self):
        super().__init__()
        # Скачиваем шрифты если их нет
        download_dejavu_fonts()
        # Добавляем шрифты
        if os.path.exists('/tmp/DejaVuSans.ttf'):
            self.add_font('DejaVu', '', '/tmp/DejaVuSans.ttf', uni=True)
        if os.path.exists('/tmp/DejaVuSans-Bold.ttf'):
            self.add_font('DejaVu', 'B', '/tmp/DejaVuSans-Bold.ttf', uni=True)

def generate_pdf(all_routes_df, routes_list, driver, car, plomb):
    """Генерирует PDF с помощью FPDF (отличная поддержка русского языка)"""
    
    buffer = BytesIO()
    
    # Создаем PDF в альбомной ориентации
    pdf = RussianPDF()
    pdf.add_page(orientation='L')
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # Проверяем, загрузился ли шрифт, если нет - используем стандартный
    try:
        pdf.set_font('DejaVu', '', 12)
    except:
        pdf.set_font('Helvetica', '', 12)
    
    # Случайный номер
    random_num = random.randint(10000, 99999)
    
    # Общая статистика
    total_boxes = int(all_routes_df["кол-во штук в заказе"].sum())
    total_stores = len(all_routes_df)
    
    # ЗАГОЛОВОК
    try:
        pdf.set_font('DejaVu', 'B', 20)
    except:
        pdf.set_font('Helvetica', 'B', 20)
    pdf.cell(0, 15, 'МАРШРУТНЫЙ ЛИСТ', ln=True, align='C')
    pdf.ln(5)
    
    # Номер
    try:
        pdf.set_font('DejaVu', '', 12)
    except:
        pdf.set_font('Helvetica', '', 12)
    pdf.cell(0, 8, f'№ {random_num}', ln=True, align='L')
    pdf.ln(5)
    
    # Информация о рейсе
    pdf.cell(0, 8, f'Водитель: {driver}', ln=True)
    pdf.cell(0, 8, f'А/м гос номер: {car}', ln=True)
    pdf.cell(0, 8, f'Дата: {datetime.now().strftime("%d.%m.%Y")}', ln=True)
    pdf.cell(0, 8, f'№ пломбы: {plomb}', ln=True)
    pdf.ln(5)
    
    # Сводка по маршрутам
    try:
        pdf.set_font('DejaVu', 'B', 11)
    except:
        pdf.set_font('Helvetica', 'B', 11)
    pdf.cell(0, 8, 'Маршруты в рейсе:', ln=True)
    
    try:
        pdf.set_font('DejaVu', '', 10)
    except:
        pdf.set_font('Helvetica', '', 10)
    for route in routes_list:
        route_data = all_routes_df[all_routes_df["Номер маршрута"] == route]
        pdf.cell(0, 6, f'• Маршрут {route} ({len(route_data)} магазинов, {int(route_data["кол-во штук в заказе"].sum())} коробок)', ln=True)
    pdf.ln(5)
    
    # Строка с коробками
    try:
        pdf.set_font('DejaVu', 'B', 11)
    except:
        pdf.set_font('Helvetica', 'B', 11)
    pdf.cell(0, 8, f'Водитель {driver} получил всего __________ коробов для {total_stores} магазинов', ln=True)
    pdf.ln(8)
    
    # ТАБЛИЦА
    # Ширина колонок (в мм) для A4 landscape (297мм)
    col_widths = [12, 25, 40, 50, 22, 22, 25, 25, 28, 28]
    
    # Заголовки
    headers = ['№', 'Заказ', 'Магазин', 'Адрес', 'Маршрут', 'Пломба', 'Коробов выдано', 'Коробов получено', 'Подпись и печать', 'Подпись водителя']
    
    try:
        pdf.set_font('DejaVu', 'B', 7)
    except:
        pdf.set_font('Helvetica', 'B', 7)
    pdf.set_fill_color(44, 62, 80)
    pdf.set_text_color(255, 255, 255)
    
    # Рисуем заголовки
    for i, header in enumerate(headers):
        pdf.cell(col_widths[i], 10, header, border=1, align='C', fill=True)
    pdf.ln()
    
    # Данные
    try:
        pdf.set_font('DejaVu', '', 7)
    except:
        pdf.set_font('Helvetica', '', 7)
    pdf.set_text_color(0, 0, 0)
    pdf.set_fill_color(255, 255, 255)
    
    for idx, (_, row) in enumerate(all_routes_df.iterrows(), start=1):
        # Ограничиваем длину текста
        shop_name = str(row.get("Название магазина", ""))[:30]
        address = str(row.get("Адрес магазина", ""))[:40]
        
        # Рисуем ячейки
        pdf.cell(col_widths[0], 8, str(idx), border=1, align='C')
        pdf.cell(col_widths[1], 8, str(row.get("№ заказа", ""))[:15], border=1, align='C')
        pdf.cell(col_widths[2], 8, shop_name, border=1, align='L')
        pdf.cell(col_widths[3], 8, address, border=1, align='L')
        pdf.cell(col_widths[4], 8, str(row.get("Номер маршрута", "")), border=1, align='C')
        pdf.cell(col_widths[5], 8, plomb, border=1, align='C')
        pdf.cell(col_widths[6], 8, str(int(row.get("кол-во штук в заказе", 0))), border=1, align='C')
        pdf.cell(col_widths[7], 8, '________', border=1, align='C')
        pdf.cell(col_widths[8], 8, '_________', border=1, align='C')
        pdf.cell(col_widths[9], 8, '_________', border=1, align='C')
        pdf.ln()
    
    pdf.ln(8)
    
    # Итого
    try:
        pdf.set_font('DejaVu', 'B', 11)
    except:
        pdf.set_font('Helvetica', 'B', 11)
    pdf.cell(0, 8, f'Итого коробов по всем маршрутам: {total_boxes}', ln=True)
    pdf.ln(15)
    
    # Подписи
    try:
        pdf.set_font('DejaVu', '', 11)
    except:
        pdf.set_font('Helvetica', '', 11)
    pdf.cell(0, 8, 'Подпись водителя: ___________________________', ln=True)
    pdf.cell(0, 8, 'Подпись принимающей стороны: ___________________________', ln=True)
    pdf.cell(0, 8, 'Печать: ___________________________', ln=True)
    pdf.ln(8)
    pdf.cell(0, 8, f'Дата: {datetime.now().strftime("%d.%m.%Y")}', ln=True)
    
    # Сохраняем в буфер
    pdf.output(buffer)
    buffer.seek(0)
    
    return buffer

# ---------------- UI ----------------

st.title("🚚 Система управления отгрузкой маршрутов")
st.markdown("---")

try:
    df = get_data()
except Exception as e:
    st.error(f"❌ Ошибка подключения к Google Sheets: {str(e)}")
    st.stop()

# Фильтрация данных
if "Статус отгрузки" in df.columns:
    not_shipped = df[df["Статус отгрузки"] != "ОТГРУЖЕН"]
    shipped = df[df["Статус отгрузки"] == "ОТГРУЖЕН"]
else:
    not_shipped = df.copy()
    shipped = pd.DataFrame()

# ---------------- METRICS ----------------
st.subheader("📊 Сводная информация")

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric("🚫 Не отгружено маршрутов", not_shipped["Номер маршрута"].nunique() if len(not_shipped) > 0 else 0)

with col2:
    st.metric("✅ Отгружено маршрутов", shipped["Номер маршрута"].nunique() if len(shipped) > 0 else 0)

with col3:
    st.metric("📍 Всего точек доставки", len(not_shipped))

with col4:
    total_boxes = not_shipped["кол-во штук в заказе"].sum() if len(not_shipped) > 0 else 0
    st.metric("📦 Всего коробок к отгрузке", int(total_boxes))

with col5:
    if len(df) > 0 and df["Номер маршрута"].nunique() > 0:
        completion_rate = (shipped["Номер маршрута"].nunique() / df["Номер маршрута"].nunique() * 100)
    else:
        completion_rate = 0
    st.metric("📈 Прогресс отгрузки", f"{completion_rate:.1f}%")

st.markdown("---")

# ---------------- SIDEBAR ----------------
with st.sidebar:
    st.header("🔍 Детальная информация")
    
    view_type = st.radio("Показать:", ["Неотгруженные маршруты", "Отгруженные маршруты", "Все маршруты"])
    
    if view_type == "Неотгруженные маршруты":
        display_df = not_shipped
    elif view_type == "Отгруженные маршруты":
        display_df = shipped
    else:
        display_df = df
    
    if len(display_df) > 0:
        route_summary = display_df.groupby("Номер маршрута").agg({
            "№ заказа": "count",
            "кол-во штук в заказе": "sum"
        }).rename(columns={"№ заказа": "Кол-во заказов", "кол-во штук в заказе": "Коробок"})
        
        st.dataframe(route_summary, use_container_width=True)
        
        if len(route_summary) > 0:
            selected_route = st.selectbox("Выберите маршрут для детализации", route_summary.index)
            if selected_route:
                route_details = display_df[display_df["Номер маршрута"] == selected_route]
                st.markdown("**Состав маршрута:**")
                st.dataframe(
                    route_details[["№ заказа", "Название магазина", "Адрес магазина", "кол-во штук в заказе"]],
                    use_container_width=True,
                    hide_index=True
                )

st.markdown("---")

# ---------------- SHIPMENT FORM ----------------
st.subheader("🚛 Отгрузка маршрутов")

col1, col2, col3 = st.columns(3)

with col1:
    car_number = st.text_input("🚐 Номер машины", placeholder="А123ВС77")

with col2:
    driver = st.text_input("👤 Водитель", placeholder="Фамилия И.О.")

with col3:
    plomb = st.text_input("🔒 № пломбы", placeholder="номер пломбы")

st.markdown("---")

# Выбор маршрутов
not_shipped_routes = sorted(not_shipped["Номер маршрута"].dropna().unique()) if len(not_shipped) > 0 else []

if len(not_shipped_routes) > 0:
    st.subheader("📋 Выберите маршруты для отгрузки")
    
    selected_routes = st.multiselect(
        "Маршруты, готовые к отгрузке:",
        options=not_shipped_routes,
        format_func=lambda x: f"🗺️ Маршрут {x}"
    )
    
    if selected_routes:
        st.markdown("### 📦 Детали выбранных маршрутов")
        
        details_df = not_shipped[not_shipped["Номер маршрута"].isin(selected_routes)]
        
        total_selected_boxes = int(details_df["кол-во штук в заказе"].sum())
        total_selected_stores = len(details_df)
        
        st.info(f"📊 Выбрано {len(selected_routes)} маршрутов | {total_selected_stores} магазинов | {total_selected_boxes} коробок")
        
        for route in selected_routes:
            route_data = details_df[details_df["Номер маршрута"] == route]
            total_boxes_route = int(route_data["кол-во штук в заказе"].sum())
            
            with st.expander(f"🗺️ Маршрут {route} - {len(route_data)} магазинов, {total_boxes_route} коробок", expanded=False):
                st.dataframe(
                    route_data[["№ заказа", "Название магазина", "Адрес магазина", "кол-во штук в заказе"]],
                    use_container_width=True,
                    hide_index=True
                )
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            ship_button = st.button("✅ ОТГРУЗИТЬ ВЫБРАННЫЕ МАРШРУТЫ", type="primary", use_container_width=True)
        
        if ship_button:
            if not car_number:
                st.error("❌ Введите номер машины!")
                st.stop()
            
            if not driver:
                st.error("❌ Введите ФИО водителя!")
                st.stop()
            
            if not plomb:
                st.warning("⚠️ Рекомендуется указать номер пломбы!")
            
            selected_data = df[df["Номер маршрута"].isin(selected_routes)]
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i, route in enumerate(selected_routes):
                status_text.text(f"Отгрузка маршрута {route}...")
                update_route(route, car_number, driver, plomb)
                progress_bar.progress((i + 1) / len(selected_routes))
            
            status_text.text("Генерация маршрутного листа...")
            pdf_buffer = generate_pdf(selected_data, selected_routes, driver, car_number, plomb)
            
            status_text.text("✅ Отгрузка завершена!")
            
            st.success(f"✅ Успешно отгружено {len(selected_routes)} маршрутов!")
            
            st.subheader("📄 Скачать маршрутный лист")
            
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                st.download_button(
                    label="📄 Скачать маршрутный лист (PDF)",
                    data=pdf_buffer,
                    file_name=f"Маршрутный_лист_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
            
            if st.button("🔄 Обновить данные", key="refresh"):
                st.rerun()
else:
    st.info("🎉 Все маршруты отгружены! Отличная работа!")

st.markdown("---")
st.caption(f"Последнее обновление: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")

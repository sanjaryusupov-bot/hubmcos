import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from io import BytesIO
import random
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
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

# ---------------- DOWNLOAD FONT ----------------

def download_font():
    """Скачивает шрифт DejaVuSans для поддержки русского языка"""
    font_url = "https://github.com/dejavu-fonts/dejavu-fonts/raw/master/ttf/DejaVuSans.ttf"
    font_path = "/tmp/DejaVuSans.ttf"
    
    if not os.path.exists(font_path):
        try:
            urllib.request.urlretrieve(font_url, font_path)
            return font_path
        except:
            return None
    return font_path

# Регистрируем шрифт
font_path = download_font()
if font_path and os.path.exists(font_path):
    try:
        pdfmetrics.registerFont(TTFont('DejaVu', font_path))
        RUSSIAN_FONT_AVAILABLE = True
    except:
        RUSSIAN_FONT_AVAILABLE = False
else:
    RUSSIAN_FONT_AVAILABLE = False

# ---------------- PDF GENERATION WITH REPORTLAB ----------------

def generate_pdf(all_routes_df, routes_list, driver, car, plomb):
    """Генерирует PDF с поддержкой русского языка через reportlab"""
    buffer = BytesIO()
    
    # Создаем PDF в альбомной ориентации
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=15*mm,
        leftMargin=15*mm,
        topMargin=15*mm,
        bottomMargin=15*mm
    )
    
    # Контейнер для элементов
    story = []
    
    # Случайный номер
    random_num = random.randint(10000, 99999)
    
    # Общая статистика
    total_boxes = int(all_routes_df["кол-во штук в заказе"].sum())
    total_stores = len(all_routes_df)
    
    # Используем canvas для прямой отрисовки (лучше для русского языка)
    def draw_pdf(c):
        y = 280  # Начальная позиция по Y (сверху)
        x_start = 20
        
        # Заголовок
        if RUSSIAN_FONT_AVAILABLE:
            c.setFont('DejaVu', 18)
        else:
            c.setFont('Helvetica-Bold', 18)
        c.drawCentredString(150, y, "МАРШРУТНЫЙ ЛИСТ")
        y -= 15
        
        # Номер
        if RUSSIAN_FONT_AVAILABLE:
            c.setFont('DejaVu', 11)
        else:
            c.setFont('Helvetica', 11)
        c.drawString(x_start, y, f"№ {random_num}")
        y -= 12
        
        # Информация о рейсе
        c.drawString(x_start, y, f"Водитель: {driver}")
        y -= 8
        c.drawString(x_start, y, f"А/м гос номер: {car}")
        y -= 8
        c.drawString(x_start, y, f"Дата: {datetime.now().strftime('%d.%m.%Y')}")
        y -= 8
        c.drawString(x_start, y, f"№ пломбы: {plomb}")
        y -= 15
        
        # Маршруты в рейсе
        if RUSSIAN_FONT_AVAILABLE:
            c.setFont('DejaVu', 10)
        else:
            c.setFont('Helvetica-Bold', 10)
        c.drawString(x_start, y, "Маршруты в рейсе:")
        y -= 8
        
        if RUSSIAN_FONT_AVAILABLE:
            c.setFont('DejaVu', 9)
        else:
            c.setFont('Helvetica', 9)
        for route in routes_list:
            route_data = all_routes_df[all_routes_df["Номер маршрута"] == route]
            text = f"• Маршрут {route} ({len(route_data)} магазинов, {int(route_data['кол-во штук в заказе'].sum())} коробок)"
            c.drawString(x_start + 5, y, text)
            y -= 7
        y -= 8
        
        # Строка с коробками
        if RUSSIAN_FONT_AVAILABLE:
            c.setFont('DejaVu', 10)
        else:
            c.setFont('Helvetica-Bold', 10)
        c.drawString(x_start, y, f"Водитель {driver} получил всего __________ коробов для {total_stores} магазинов")
        y -= 20
        
        # Заголовки таблицы
        headers = [
            "№", "Заказ", "Магазин", "Адрес", "Маршрут", "Пломба",
            "Коробов\nвыдано", "Коробов\nполучено", "Подпись и\nпечать", "Подпись\nводителя"
        ]
        
        col_widths = [12, 25, 40, 50, 20, 20, 18, 18, 25, 25]
        x = x_start
        
        # Рисуем заголовки
        if RUSSIAN_FONT_AVAILABLE:
            c.setFont('DejaVu', 7)
        else:
            c.setFont('Helvetica-Bold', 7)
        c.setFillColor(colors.white)
        c.setFillColorRGB(0.17, 0.24, 0.31)  # #2c3e50
        
        for i, header in enumerate(headers):
            c.rect(x, y - 8, col_widths[i], 10, fill=True)
            c.setFillColor(colors.white)
            c.drawCentredString(x + col_widths[i]/2, y - 3, header)
            x += col_widths[i]
        
        c.setFillColor(colors.black)
        y -= 10
        
        # Данные
        if RUSSIAN_FONT_AVAILABLE:
            c.setFont('DejaVu', 6)
        else:
            c.setFont('Helvetica', 6)
        
        for idx, (_, row) in enumerate(all_routes_df.iterrows(), start=1):
            x = x_start
            if y < 50:  # Новая страница
                c.showPage()
                y = 280
                # Переносим заголовки на новую страницу
                x = x_start
                if RUSSIAN_FONT_AVAILABLE:
                    c.setFont('DejaVu', 7)
                else:
                    c.setFont('Helvetica-Bold', 7)
                c.setFillColorRGB(0.17, 0.24, 0.31)
                for i, header in enumerate(headers):
                    c.rect(x, y - 8, col_widths[i], 10, fill=True)
                    c.setFillColor(colors.white)
                    c.drawCentredString(x + col_widths[i]/2, y - 3, header)
                    x += col_widths[i]
                c.setFillColor(colors.black)
                y -= 10
                if RUSSIAN_FONT_AVAILABLE:
                    c.setFont('DejaVu', 6)
                else:
                    c.setFont('Helvetica', 6)
                x = x_start
            
            shop_name = str(row.get("Название магазина", ""))[:25]
            address = str(row.get("Адрес магазина", ""))[:35]
            
            c.rect(x, y - 6, col_widths[0], 7)
            c.drawCentredString(x + col_widths[0]/2, y - 2, str(idx))
            x += col_widths[0]
            
            c.rect(x, y - 6, col_widths[1], 7)
            c.drawCentredString(x + col_widths[1]/2, y - 2, str(row.get("№ заказа", ""))[:12])
            x += col_widths[1]
            
            c.rect(x, y - 6, col_widths[2], 7)
            c.drawString(x + 2, y - 2, shop_name)
            x += col_widths[2]
            
            c.rect(x, y - 6, col_widths[3], 7)
            c.drawString(x + 2, y - 2, address)
            x += col_widths[3]
            
            c.rect(x, y - 6, col_widths[4], 7)
            c.drawCentredString(x + col_widths[4]/2, y - 2, str(row.get("Номер маршрута", "")))
            x += col_widths[4]
            
            c.rect(x, y - 6, col_widths[5], 7)
            c.drawCentredString(x + col_widths[5]/2, y - 2, plomb)
            x += col_widths[5]
            
            c.rect(x, y - 6, col_widths[6], 7)
            c.drawCentredString(x + col_widths[6]/2, y - 2, str(int(row.get("кол-во штук в заказе", 0))))
            x += col_widths[6]
            
            c.rect(x, y - 6, col_widths[7], 7)
            c.drawCentredString(x + col_widths[7]/2, y - 2, "_____")
            x += col_widths[7]
            
            c.rect(x, y - 6, col_widths[8], 7)
            c.drawCentredString(x + col_widths[8]/2, y - 2, "______")
            x += col_widths[8]
            
            c.rect(x, y - 6, col_widths[9], 7)
            c.drawCentredString(x + col_widths[9]/2, y - 2, "______")
            
            y -= 8
        
        y -= 15
        
        # Итого
        if RUSSIAN_FONT_AVAILABLE:
            c.setFont('DejaVu', 10)
        else:
            c.setFont('Helvetica-Bold', 10)
        c.drawString(x_start, y, f"Итого коробов по всем маршрутам: {total_boxes}")
        y -= 20
        
        # Подписи
        if RUSSIAN_FONT_AVAILABLE:
            c.setFont('DejaVu', 9)
        else:
            c.setFont('Helvetica', 9)
        c.drawString(x_start, y, "Подпись водителя: ___________________________")
        y -= 8
        c.drawString(x_start, y, "Подпись принимающей стороны: ___________________________")
        y -= 8
        c.drawString(x_start, y, "Печать: ___________________________")
        y -= 12
        c.drawString(x_start, y, f"Дата: {datetime.now().strftime('%d.%m.%Y')}")
    
    # Строим PDF
    doc.build(story, onFirstPage=draw_pdf, onLaterPages=draw_pdf)
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

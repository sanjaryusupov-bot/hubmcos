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

# ---------------- PDF GENERATION WITH FULL PAGE USAGE ----------------

def draw_text_with_wrap(c, text, x, y, max_width, font_name, font_size, line_height=10):
    """Рисует текст с переносом строк"""
    c.setFont(font_name, font_size)
    words = text.split()
    lines = []
    current_line = []
    
    for word in words:
        test_line = ' '.join(current_line + [word])
        text_width = c.stringWidth(test_line, font_name, font_size)
        if text_width <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(' '.join(current_line))
            current_line = [word]
    
    if current_line:
        lines.append(' '.join(current_line))
    
    for i, line in enumerate(lines):
        c.drawString(x, y - (i * line_height), line)
    
    return len(lines) * line_height

def generate_pdf(all_routes_df, routes_list, driver, car, plomb):
    buffer = BytesIO()
    
    # Получаем размеры страницы A4 landscape
    width, height = landscape(A4)  # 297mm x 210mm
    left_margin = 10
    right_margin = width - 10
    top_margin = height - 10
    bottom_margin = 10
    
    # Создаем PDF
    c = canvas.Canvas(buffer, pagesize=landscape(A4))
    
    # Используем стандартные шрифты с поддержкой кириллицы через кодировку
    # Вместо этого будем использовать методы рисования текста
    y = top_margin - 10
    
    # ЗАГОЛОВОК
    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(width/2, y, "МАРШРУТНЫЙ ЛИСТ")
    y -= 20
    
    # Номер документа
    random_num = random.randint(10000, 99999)
    c.setFont("Helvetica", 11)
    c.drawString(left_margin, y, f"№ {random_num}")
    y -= 15
    
    # Информационная таблица
    c.setFont("Helvetica", 10)
    info_data = [
        f"Водитель: {driver}",
        f"А/м гос номер: {car}",
        f"Дата: {datetime.now().strftime('%d.%m.%Y')}",
        f"№ пломбы: {plomb}"
    ]
    
    for line in info_data:
        c.drawString(left_margin, y, line)
        y -= 12
    y -= 5
    
    # Маршруты в рейсе
    c.setFont("Helvetica-Bold", 10)
    c.drawString(left_margin, y, "Маршруты в рейсе:")
    y -= 12
    
    c.setFont("Helvetica", 9)
    for route in routes_list:
        route_data = all_routes_df[all_routes_df["Номер маршрута"] == route]
        route_text = f"• Маршрут {route} ({len(route_data)} магазинов, {int(route_data['кол-во штук в заказе'].sum())} коробок)"
        c.drawString(left_margin + 5, y, route_text)
        y -= 10
    y -= 5
    
    # Строка с коробками
    c.setFont("Helvetica-Bold", 10)
    total_stores = len(all_routes_df)
    c.drawString(left_margin, y, f"Водитель {driver} получил всего __________ коробов для {total_stores} магазинов")
    y -= 25
    
    # Параметры таблицы
    col_widths = [20, 35, 45, 55, 25, 25, 25, 25, 30, 30]
    headers = [
        "№", "Заказ", "Магазин", "Адрес",
        "Маршрут", "Пломба", "Коробов\nвыдано", "Коробов\nполучено",
        "Подпись и\nпечать", "Подпись\nводителя"
    ]
    
    # Рисуем заголовки таблицы
    c.setFont("Helvetica-Bold", 7)
    c.setFillColorRGB(0.2, 0.3, 0.4)
    
    x = left_margin
    for i, header in enumerate(headers):
        c.rect(x, y - 15, col_widths[i], 15, fill=True)
        c.setFillColorRGB(1, 1, 1)
        
        # Разбиваем заголовок на строки
        if '\n' in header:
            lines = header.split('\n')
            c.drawCentredString(x + col_widths[i]/2, y - 8, lines[0])
            c.drawCentredString(x + col_widths[i]/2, y - 2, lines[1])
        else:
            c.drawCentredString(x + col_widths[i]/2, y - 8, header)
        
        c.setFillColorRGB(0, 0, 0)
        x += col_widths[i]
    
    y -= 15
    x = left_margin
    
    # Данные таблицы
    c.setFont("Helvetica", 6)
    row_num = 1
    
    for idx, (_, row) in enumerate(all_routes_df.iterrows(), start=1):
        x = left_margin
        
        # Проверка на новую страницу
        if y < bottom_margin + 50:
            c.showPage()
            y = top_margin - 10
            x = left_margin
            
            # Перерисовываем заголовки
            c.setFont("Helvetica-Bold", 7)
            c.setFillColorRGB(0.2, 0.3, 0.4)
            for i, header in enumerate(headers):
                c.rect(x, y - 15, col_widths[i], 15, fill=True)
                c.setFillColorRGB(1, 1, 1)
                if '\n' in header:
                    lines = header.split('\n')
                    c.drawCentredString(x + col_widths[i]/2, y - 8, lines[0])
                    c.drawCentredString(x + col_widths[i]/2, y - 2, lines[1])
                else:
                    c.drawCentredString(x + col_widths[i]/2, y - 8, header)
                c.setFillColorRGB(0, 0, 0)
                x += col_widths[i]
            y -= 15
            c.setFont("Helvetica", 6)
            x = left_margin
        
        # Номер
        c.rect(x, y - 10, col_widths[0], 10)
        c.drawCentredString(x + col_widths[0]/2, y - 5, str(idx))
        x += col_widths[0]
        
        # Заказ
        c.rect(x, y - 10, col_widths[1], 10)
        c.drawCentredString(x + col_widths[1]/2, y - 5, str(row.get("№ заказа", ""))[:15])
        x += col_widths[1]
        
        # Магазин
        c.rect(x, y - 10, col_widths[2], 10)
        shop_name = str(row.get("Название магазина", ""))[:25]
        c.drawString(x + 2, y - 5, shop_name)
        x += col_widths[2]
        
        # Адрес
        c.rect(x, y - 10, col_widths[3], 10)
        address = str(row.get("Адрес магазина", ""))[:35]
        c.drawString(x + 2, y - 5, address)
        x += col_widths[3]
        
        # Маршрут
        c.rect(x, y - 10, col_widths[4], 10)
        c.drawCentredString(x + col_widths[4]/2, y - 5, str(row.get("Номер маршрута", ""))[:10])
        x += col_widths[4]
        
        # Пломба
        c.rect(x, y - 10, col_widths[5], 10)
        c.drawCentredString(x + col_widths[5]/2, y - 5, plomb[:10])
        x += col_widths[5]
        
        # Коробов выдано
        c.rect(x, y - 10, col_widths[6], 10)
        c.drawCentredString(x + col_widths[6]/2, y - 5, str(int(row.get("кол-во штук в заказе", 0))))
        x += col_widths[6]
        
        # Коробов получено
        c.rect(x, y - 10, col_widths[7], 10)
        c.drawCentredString(x + col_widths[7]/2, y - 5, "_____")
        x += col_widths[7]
        
        # Подпись и печать
        c.rect(x, y - 10, col_widths[8], 10)
        c.drawCentredString(x + col_widths[8]/2, y - 5, "______")
        x += col_widths[8]
        
        # Подпись водителя
        c.rect(x, y - 10, col_widths[9], 10)
        c.drawCentredString(x + col_widths[9]/2, y - 5, "______")
        
        y -= 12
    
    y -= 15
    
    # Итоговая строка
    c.setFont("Helvetica-Bold", 10)
    total_boxes = int(all_routes_df["кол-во штук в заказе"].sum())
    c.drawString(left_margin, y, f"Итого коробов по всем маршрутам: {total_boxes}")
    y -= 25
    
    # Подписи
    c.setFont("Helvetica", 9)
    c.drawString(left_margin, y, "Подпись водителя: ___________________________")
    y -= 12
    c.drawString(left_margin, y, "Подпись принимающей стороны: ___________________________")
    y -= 12
    c.drawString(left_margin, y, "Печать: ___________________________")
    y -= 15
    c.drawString(left_margin, y, f"Дата: {datetime.now().strftime('%d.%m.%Y')}")
    
    c.save()
    buffer.seek(0)
    return buffer

# ---------------- UI ----------------

st.title("🚚 Система управления отгрузкой маршрутов")
st.markdown("---")

try:
    df = get_data()
except Exception as e:
    st.error(f"Ошибка: {str(e)}")
    st.stop()

if "Статус отгрузки" in df.columns:
    not_shipped = df[df["Статус отгрузки"] != "ОТГРУЖЕН"]
    shipped = df[df["Статус отгрузки"] == "ОТГРУЖЕН"]
else:
    not_shipped = df.copy()
    shipped = pd.DataFrame()

# Метрики
col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.metric("Не отгружено", not_shipped["Номер маршрута"].nunique() if len(not_shipped) > 0 else 0)
with col2:
    st.metric("Отгружено", shipped["Номер маршрута"].nunique() if len(shipped) > 0 else 0)
with col3:
    st.metric("Точек доставки", len(not_shipped))
with col4:
    total_boxes = not_shipped["кол-во штук в заказе"].sum() if len(not_shipped) > 0 else 0
    st.metric("Коробок к отгрузке", int(total_boxes))
with col5:
    completion = (shipped["Номер маршрута"].nunique() / df["Номер маршрута"].nunique() * 100) if len(df) > 0 and df["Номер маршрута"].nunique() > 0 else 0
    st.metric("Прогресс", f"{completion:.1f}%")

st.markdown("---")

# Боковая панель с деталями
with st.sidebar:
    st.header("Детальная информация")
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
        }).rename(columns={"№ заказа": "Заказов", "кол-во штук в заказе": "Коробок"})
        st.dataframe(route_summary, use_container_width=True)

st.markdown("---")

# Форма отгрузки
st.subheader("Отгрузка маршрутов")

col1, col2, col3 = st.columns(3)
with col1:
    car_number = st.text_input("Номер машины", placeholder="А123ВС77")
with col2:
    driver = st.text_input("Водитель", placeholder="Иванов И.И.")
with col3:
    plomb = st.text_input("№ пломбы", placeholder="12345")

st.markdown("---")

# Выбор маршрутов
not_shipped_routes = sorted(not_shipped["Номер маршрута"].dropna().unique()) if len(not_shipped) > 0 else []

if len(not_shipped_routes) > 0:
    st.subheader("Выберите маршруты для отгрузки")
    selected_routes = st.multiselect("Маршруты:", options=not_shipped_routes)
    
    if selected_routes:
        details_df = not_shipped[not_shipped["Номер маршрута"].isin(selected_routes)]
        st.info(f"✅ Выбрано {len(selected_routes)} маршрутов | {len(details_df)} магазинов | {int(details_df['кол-во штук в заказе'].sum())} коробок")
        
        # Показываем детали выбранных маршрутов
        for route in selected_routes:
            route_data = details_df[details_df["Номер маршрута"] == route]
            with st.expander(f"Маршрут {route} - {len(route_data)} магазинов, {int(route_data['кол-во штук в заказе'].sum())} коробок"):
                st.dataframe(route_data[["№ заказа", "Название магазина", "Адрес магазина", "кол-во штук в заказе"]], 
                           use_container_width=True, hide_index=True)
        
        if st.button("✅ ОТГРУЗИТЬ ВЫБРАННЫЕ МАРШРУТЫ", type="primary", use_container_width=True):
            if not car_number:
                st.error("❌ Введите номер машины!")
                st.stop()
            if not driver:
                st.error("❌ Введите ФИО водителя!")
                st.stop()
            
            selected_data = df[df["Номер маршрута"].isin(selected_routes)]
            
            # Обновляем статусы
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
                    label="📄 Скачать PDF",
                    data=pdf_buffer,
                    file_name=f"Маршрутный_лист_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
            
            if st.button("🔄 Обновить данные"):
                st.rerun()
else:
    st.info("🎉 Все маршруты отгружены! Отличная работа!")

st.markdown("---")
st.caption(f"Последнее обновление: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")

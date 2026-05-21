# app.py

import streamlit as st
import pandas as pd
import gspread
import tempfile
import os

from datetime import datetime

from oauth2client.service_account import ServiceAccountCredentials

from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
    HRFlowable
)

from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm

from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase import pdfmetrics

# ---------------- PDF FONT ----------------

pdfmetrics.registerFont(
    UnicodeCIDFont('HYSMyeongJo-Medium')
)

# ---------------- PAGE ----------------

st.set_page_config(
    page_title="🚚 Отгрузка маршрутов",
    layout="wide"
)

# ---------------- SETTINGS ----------------

SHEET_ID = "1hKZ8ggNLW-OY1bV8xAW7PKl50Fof2co86oxGK92YPAA"
SHEET_NAME = "Маршруты"

# Session state для контроля отгрузки
if 'shipment_completed' not in st.session_state:
    st.session_state.shipment_completed = False

if 'pdf_generated' not in st.session_state:
    st.session_state.pdf_generated = False

# ---------------- CSS ----------------

st.markdown("""
<style>

.main {
    background-color: #F3F4F6;
}

div[data-testid="metric-container"] {
    background: white;
    border-radius: 16px;
    padding: 20px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.05);
}

.stButton>button {
    background-color: #16A34A;
    color: white;
    border-radius: 12px;
    border: none;
    padding: 14px 22px;
    font-weight: 700;
    width: 100%;
    font-size: 16px;
}

.stButton>button:hover {
    background-color: #15803D;
}

.stButton>button:disabled {
    background-color: #94A3B8;
    cursor: not-allowed;
}

div[data-testid="stDownloadButton"] > button {
    background-color: #3B82F6;
    color: white;
    border-radius: 12px;
    border: none;
    padding: 14px 22px;
    font-weight: 700;
    width: 100%;
    font-size: 16px;
}

div[data-testid="stDownloadButton"] > button:hover {
    background-color: #2563EB;
}

</style>
""", unsafe_allow_html=True)

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

    sheet = client.open_by_key(
        SHEET_ID
    ).worksheet(
        SHEET_NAME
    )

    return sheet

def get_data():
    sheet = connect_sheet()
    data = sheet.get_all_records()
    return pd.DataFrame(data)

def update_route(route_name, car_number, driver, plomb):
    sheet = connect_sheet()
    data = sheet.get_all_records()
    headers = sheet.row_values(1)

    extra_columns = [
        "Номер машины",
        "Водитель",
        "№ пломбы",
        "Дата отгрузки факт"
    ]

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
        if row["Номер маршрута"] == route_name:
            sheet.update_cell(idx, status_col, "ОТГРУЖЕН")
            sheet.update_cell(idx, fact_col, datetime.now().strftime("%d.%m.%Y %H:%M"))
            sheet.update_cell(idx, car_col, car_number)
            sheet.update_cell(idx, driver_col, driver)
            sheet.update_cell(idx, plomb_col, plomb)

# ---------------- PDF GENERATION ----------------

def generate_delivery_pdf(df, route, driver, car, plomb):
    """Генерация PDF для нескольких магазинов"""
    
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
        filename = tmp_file.name
    
    doc = SimpleDocTemplate(
        filename,
        pagesize=landscape(A4),
        leftMargin=8*mm,
        rightMargin=8*mm,
        topMargin=12*mm,
        bottomMargin=12*mm
    )

    styles = getSampleStyleSheet()
    
    # Стили для кириллицы
    styleTitle = ParagraphStyle(
        'CustomTitle',
        parent=styles['Normal'],
        fontName='HYSMyeongJo-Medium',
        fontSize=14,
        leading=18,
        alignment=1,  # Center
        spaceAfter=8,
        spaceBefore=5
    )
    
    styleInfo = ParagraphStyle(
        'CustomInfo',
        parent=styles['Normal'],
        fontName='HYSMyeongJo-Medium',
        fontSize=9,
        leading=11
    )
    
    styleHeader = ParagraphStyle(
        'CustomHeader',
        parent=styles['Normal'],
        fontName='HYSMyeongJo-Medium',
        fontSize=8,
        leading=10,
        alignment=1
    )
    
    styleCell = ParagraphStyle(
        'CustomCell',
        parent=styles['Normal'],
        fontName='HYSMyeongJo-Medium',
        fontSize=7,
        leading=9
    )
    
    styleBold = ParagraphStyle(
        'CustomBold',
        parent=styles['Normal'],
        fontName='HYSMyeongJo-Medium',
        fontSize=7,
        leading=9
    )

    elements = []
    
    total_points = len(df)

    # Заголовок
    title = Paragraph("<b>МАРШРУТНЫЙ ЛИСТ ДОСТАВКИ</b>", styleTitle)
    elements.append(title)
    elements.append(Spacer(1, 5))
    
    # Информация о маршруте в одной строке
    route_info = f"<b>Маршрут:</b> {route} | <b>Дата:</b> {datetime.now().strftime('%d.%m.%Y')}"
    elements.append(Paragraph(route_info, styleInfo))
    
    driver_info = f"<b>Водитель:</b> {driver} | <b>Номер машины:</b> {car}"
    elements.append(Paragraph(driver_info, styleInfo))
    
    plomb_info = f"<b>№ пломбы:</b> {plomb} | <b>Кол-во магазинов:</b> {total_points}"
    elements.append(Paragraph(plomb_info, styleInfo))
    
    elements.append(Spacer(1, 8))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.black))
    elements.append(Spacer(1, 5))

    # Таблица с заказами
    # Заголовки таблицы
    headers = [
        "<b>№ заказа</b>",
        "<b>Магазин</b>",
        "<b>Адрес</b>",
        "<b>Маршрут</b>",
        "<b>№ пломбы</b>",
        "<b>Выдано<br/>коробок</b>",
        "<b>Получено<br/>коробок</b>",
        "<b>Подпись, печать,<br/>комментарии</b>",
        "<b>Подпись<br/>водителя</b>"
    ]
    
    table_data = [headers]

    for _, row in df.iterrows():
        # Делаем номер заказа жирным
        order_number = f"<b>{row['№ заказа']}</b>"
        
        # Ограничиваем длину текста
        shop_name = str(row["Название магазина"])[:35]
        address = str(row["Адрес магазина"])[:45]
        route_name = str(row["Номер маршрута"])
        
        table_data.append([
            Paragraph(order_number, styleBold),
            Paragraph(shop_name, styleCell),
            Paragraph(address, styleCell),
            Paragraph(route_name, styleCell),
            Paragraph(plomb, styleCell),
            Paragraph("", styleCell),
            Paragraph("", styleCell),
            Paragraph("", styleCell),
            Paragraph("", styleCell)
        ])

    # Ширина колонок для landscape A4
    table = Table(
        table_data,
        colWidths=[
            16*mm,  # № заказа
            35*mm,  # Магазин
            45*mm,  # Адрес
            18*mm,  # Маршрут
            16*mm,  # № пломбы
            16*mm,  # Выдано коробок
            16*mm,  # Получено коробок
            35*mm,  # Подпись, комментарии
            24*mm   # Подпись водителя
        ],
        repeatRows=1
    )

    table.setStyle(TableStyle([
        # Header styling
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1F2937")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'HYSMyeongJo-Medium'),
        ('FONTSIZE', (0,0), (-1,0), 7.5),
        ('ALIGN', (0,0), (-1,0), 'CENTER'),
        ('VALIGN', (0,0), (-1,0), 'MIDDLE'),
        
        # Body styling
        ('FONTNAME', (0,1), (-1,-1), 'HYSMyeongJo-Medium'),
        ('FONTSIZE', (0,1), (-1,-1), 7),
        ('VALIGN', (0,1), (-1,-1), 'TOP'),
        
        # Borders
        ('GRID', (0,0), (-1,-1), 0.3, colors.black),
        
        # Padding
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING', (0,0), (-1,-1), 2),
        ('RIGHTPADDING', (0,0), (-1,-1), 2),
        
        # Alignment
        ('ALIGN', (0,1), (0,-1), 'CENTER'),  # Order number center
        ('ALIGN', (3,1), (5,-1), 'CENTER'),  # Route, plomb, issued center
        ('ALIGN', (6,1), (8,-1), 'CENTER'),  # Received, signature, driver signature center
        
        # Left align for text columns
        ('ALIGN', (1,1), (2,-1), 'LEFT'),
    ]))

    elements.append(table)
    elements.append(Spacer(1, 10))
    
    # Примечания
    notes = Paragraph(
        "<b>Примечания:</b> • Количество коробок заполняется при отгрузке • Получение подтверждается подписью и печатью",
        styleCell
    )
    elements.append(notes)

    doc.build(elements)
    return filename

# ---------------- LOAD DATA ----------------

try:
    df = get_data()
except Exception as e:
    st.error("Ошибка подключения Google Sheets")
    st.exception(e)
    st.stop()

# ---------------- FILTERS ----------------

not_shipped = df[df["Статус отгрузки"] != "ОТГРУЖЕН"]
shipped = df[df["Статус отгрузки"] == "ОТГРУЖЕН"]

# ---------------- TITLE ----------------

st.title("🚚 Система отгрузки маршрутов")

# ---------------- METRICS ----------------

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "Не отгружено",
    not_shipped["Номер маршрута"].nunique()
)

col2.metric(
    "Отгружено",
    shipped["Номер маршрута"].nunique()
)

col3.metric(
    "Точек",
    len(not_shipped)
)

col4.metric(
    "Кол-во шт",
    int(not_shipped["кол-во штук в заказе"].sum())
)

st.divider()

# ---------------- SUMMARY NOT SHIPPED ----------------

st.subheader("📊 Итоги по неотгруженным точкам")

# Сводная таблица: группируем по магазину и адресу
summary_not_shipped = not_shipped.groupby(
    ["Название магазина", "Адрес магазина"]
)["кол-во штук в заказе"].sum().reset_index()

summary_not_shipped.columns = ["Магазин", "Адрес", "Кол-во шт"]

# Добавляем итоговую строку
total_shirts = summary_not_shipped["Кол-во шт"].sum()
summary_with_total = pd.concat([
    summary_not_shipped,
    pd.DataFrame([["ИТОГО:", "", total_shirts]], columns=summary_not_shipped.columns)
])

st.dataframe(
    summary_with_total,
    use_container_width=True,
    height=400,
    hide_index=True
)

st.divider()

# ---------------- FORM ----------------

if not st.session_state.shipment_completed:
    left, right = st.columns([1, 1])

    with left:
        st.subheader("🚛 Данные машины")
        car_number = st.text_input("Номер машины", key="car_input")
        driver = st.text_input("Водитель", key="driver_input")
        plomb = st.text_input("№ пломбы", key="plomb_input")

    with right:
        st.subheader("📦 Маршруты")
        routes = sorted(not_shipped["Номер маршрута"].dropna().unique())
        selected_routes = st.multiselect("Выберите маршруты", routes, key="routes_select")

    # ---------------- DETAILS ----------------
    if selected_routes:
        st.subheader("📋 Детали маршрутов")

        details_df = not_shipped[
            not_shipped["Номер маршрута"].isin(selected_routes)
        ]

        st.dataframe(
            details_df[[
                "№ заказа",
                "Название магазина",
                "Адрес магазина",
                "Номер маршрута",
                "кол-во штук в заказе"
            ]],
            use_container_width=True,
            height=400
        )

    # ---------------- SHIP BUTTON ----------------
    if st.button("✅ ОТГРУЗИТЬ И СОЗДАТЬ PDF"):
        if not car_number:
            st.warning("Введите номер машины")
            st.stop()

        if not driver:
            st.warning("Введите ФИО водителя")
            st.stop()

        if not plomb:
            st.warning("Введите номер пломбы")
            st.stop()

        if not selected_routes:
            st.warning("Выберите маршрут")
            st.stop()

        # Генерируем PDF для каждого маршрута
        pdf_files = []
        
        for route in selected_routes:
            route_df = df[df["Номер маршрута"] == route]
            
            # Обновляем статус в Google Sheets
            update_route(route, car_number, driver, plomb)
            
            # Генерируем PDF (все магазины маршрута в одном PDF)
            pdf_file = generate_delivery_pdf(
                route_df,
                route,
                driver,
                car_number,
                plomb
            )
            pdf_files.append((route, pdf_file))
        
        # Сохраняем файлы в session state для скачивания
        st.session_state.pdf_files = pdf_files
        st.session_state.shipment_completed = True
        st.session_state.selected_routes = selected_routes
        st.rerun()

# ---------------- DOWNLOAD SECTION ----------------
else:
    st.success("✅ Маршруты успешно отгружены!")
    st.info("📄 Скачайте PDF-листы перед продолжением работы")
    
    # Создаем колонки для кнопок скачивания
    cols = st.columns(min(len(st.session_state.pdf_files), 3))
    
    for idx, (route, pdf_file) in enumerate(st.session_state.pdf_files):
        with cols[idx % 3]:
            with open(pdf_file, "rb") as f:
                st.download_button(
                    label=f"📄 Маршрут {route}",
                    data=f,
                    file_name=f"Маршрут_{route}.pdf",
                    mime="application/pdf",
                    key=f"download_{route}"
                )
    
    st.divider()
    
    # Кнопка сброса
    if st.button("🔄 Начать новую отгрузку"):
        # Очищаем временные файлы
        for _, pdf_file in st.session_state.pdf_files:
            try:
                os.unlink(pdf_file)
            except:
                pass
        
        st.session_state.shipment_completed = False
        st.session_state.pdf_files = []
        st.session_state.selected_routes = []
        st.rerun()

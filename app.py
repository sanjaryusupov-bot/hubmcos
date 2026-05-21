# app.py

import streamlit as st
import pandas as pd
import gspread

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

# ---------------- UPDATE ROUTE ----------------

def update_route(route_name, car_number, driver, plomb, boxes_count):

    sheet = connect_sheet()

    data = sheet.get_all_records()

    headers = sheet.row_values(1)

    extra_columns = [
        "Номер машины",
        "Водитель",
        "№ пломбы",
        "Кол-во коробок (факт)"
    ]

    current_headers = headers.copy()

    for col_name in extra_columns:

        if col_name not in current_headers:

            sheet.update_cell(
                1,
                len(current_headers) + 1,
                col_name
            )

            current_headers.append(col_name)

    headers = sheet.row_values(1)

    status_col = headers.index("Статус отгрузки") + 1
    fact_col = headers.index("Дата отгрузки факт") + 1
    car_col = headers.index("Номер машины") + 1
    driver_col = headers.index("Водитель") + 1
    plomb_col = headers.index("№ пломбы") + 1
    boxes_col = headers.index("Кол-во коробок (факт)") + 1

    for idx, row in enumerate(data, start=2):

        if row["Номер маршрута"] == route_name:

            sheet.update_cell(
                idx,
                status_col,
                "ОТГРУЖЕН"
            )

            sheet.update_cell(
                idx,
                fact_col,
                datetime.now().strftime("%d.%m.%Y %H:%M")
            )

            sheet.update_cell(
                idx,
                car_col,
                car_number
            )

            sheet.update_cell(
                idx,
                driver_col,
                driver
            )

            sheet.update_cell(
                idx,
                plomb_col,
                plomb
            )
            
            sheet.update_cell(
                idx,
                boxes_col,
                boxes_count.get(row["Номер маршрута"], "")
            )

# ---------------- PDF ----------------

def generate_pdf(df, route, driver, car, plomb, boxes_count):

    filename = f"{route}.pdf"

    doc = SimpleDocTemplate(
        filename,
        pagesize=landscape(A4),
        leftMargin=15*mm,
        rightMargin=15*mm,
        topMargin=20*mm,
        bottomMargin=15*mm
    )

    styles = getSampleStyleSheet()
    
    # Создаем стили с поддержкой кириллицы
    styleN = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontName='HYSMyeongJo-Medium',
        fontSize=9,
        leading=12
    )
    
    styleH = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading1'],
        fontName='HYSMyeongJo-Medium',
        fontSize=18,
        leading=22,
        alignment=1  # Center alignment
    )
    
    styleSmall = ParagraphStyle(
        'CustomSmall',
        parent=styles['Normal'],
        fontName='HYSMyeongJo-Medium',
        fontSize=8,
        leading=10
    )

    elements = []

    total_boxes = boxes_count.get(route, 0)
    total_points = len(df)

    # ---------------- HEADER ----------------

    title = Paragraph(
        "<b>МАРШРУТНЫЙ ЛИСТ</b>",
        styleH
    )

    elements.append(title)

    elements.append(Spacer(1, 10))

    # Информация в табличном формате
    info_data = [
        ["Маршрут:", route],
        ["Дата:", datetime.now().strftime("%d.%m.%Y %H:%M")],
        ["Водитель:", driver],
        ["Номер машины:", car],
        ["№ пломбы:", plomb],
        ["Количество магазинов:", str(total_points)],
        ["Количество коробок:", str(total_boxes)]
    ]
    
    info_table = Table(info_data, colWidths=[40*mm, 100*mm])
    info_table.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), 'HYSMyeongJo-Medium'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ]))
    
    elements.append(info_table)
    elements.append(Spacer(1, 10))
    elements.append(HRFlowable(width="100%", thickness=1))
    elements.append(Spacer(1, 10))

    # ---------------- TABLE ----------------
    
    # Уменьшаем колонки для лучшего отображения
    data = [[
        "№ заказа",
        "Магазин",
        "Адрес",
        "Шт.",
        "Коробок",
        "Подпись"
    ]]

    for _, row in df.iterrows():
        # Ограничиваем длину текста
        shop_name = str(row["Название магазина"])[:30]
        address = str(row["Адрес магазина"])[:40]
        
        data.append([
            Paragraph(str(row["№ заказа"]), styleSmall),
            Paragraph(shop_name, styleSmall),
            Paragraph(address, styleSmall),
            str(row["кол-во штук в заказе"]),
            "",  # Пустое поле для ручного ввода коробок
            ""
        ])

    table = Table(
        data,
        colWidths=[
            20*mm,   # Заказ
            35*mm,   # Магазин
            50*mm,   # Адрес
            15*mm,   # Шт.
            20*mm,   # Коробок
            30*mm    # Подпись
        ]
    )

    table.setStyle(TableStyle([
        # Header
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1F2937")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'HYSMyeongJo-Medium'),
        ('FONTSIZE', (0,0), (-1,0), 9),
        ('ALIGN', (0,0), (-1,0), 'CENTER'),
        
        # Body
        ('FONTNAME', (0,1), (-1,-1), 'HYSMyeongJo-Medium'),
        ('FONTSIZE', (0,1), (-1,-1), 8),
        ('ALIGN', (0,1), (-1,-1), 'CENTER'),
        ('VALIGN', (0,1), (-1,-1), 'MIDDLE'),
        
        # Borders
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        
        # Padding
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
        
        # Left align for text columns
        ('ALIGN', (1,1), (2,-1), 'LEFT'),
    ]))

    elements.append(table)
    elements.append(Spacer(1, 15))

    sign = Paragraph(
        "<b>Подпись водителя:</b> ________________________________<br/><br/>"
        "<b>Подпись принимающей стороны:</b> ________________________________",
        styleN
    )

    elements.append(sign)

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

not_shipped = df[
    df["Статус отгрузки"] != "ОТГРУЖЕН"
]

shipped = df[
    df["Статус отгрузки"] == "ОТГРУЖЕН"
]

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
    "Коробок (план)",
    int(not_shipped["кол-во штук в заказе"].sum())
)

st.divider()

# ---------------- SUMMARY NOT SHIPPED ----------------

st.subheader("📊 Итоги по неотгруженным точкам")

summary_not_shipped = not_shipped[[
    "Название магазина",
    "Адрес магазина",
    "кол-во штук в заказе"
]].copy()

summary_not_shipped.columns = ["Точка", "Адрес", "Кол-во шт"]

st.dataframe(
    summary_not_shipped,
    use_container_width=True,
    height=300,
    hide_index=True
)

st.divider()

# ---------------- FORM ----------------

left, right = st.columns([1, 1])

with left:
    st.subheader("🚛 Данные машины")
    car_number = st.text_input("Номер машины")
    driver = st.text_input("Водитель")
    plomb = st.text_input("№ пломбы")

with right:
    st.subheader("📦 Маршруты")
    routes = sorted(not_shipped["Номер маршрута"].dropna().unique())
    selected_routes = st.multiselect("Выберите маршруты", routes)

# ---------------- MANUAL BOXES INPUT ----------------

boxes_input = {}

if selected_routes:
    st.subheader("📦 Ручной ввод количества коробок")
    
    for route in selected_routes:
        route_df = not_shipped[not_shipped["Номер маршрута"] == route]
        total_shirts = int(route_df["кол-во штук в заказе"].sum())
        
        col1, col2 = st.columns([1, 1])
        with col1:
            st.write(f"**Маршрут {route}**")
            st.write(f"📦 План по штукам: {total_shirts}")
        
        with col2:
            boxes_input[route] = st.number_input(
                f"Кол-во коробок для маршрута {route}",
                min_value=0,
                value=0,
                step=1,
                key=f"boxes_{route}"
            )

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
    
    # Проверка ввода коробок
    missing_boxes = [route for route in selected_routes if boxes_input.get(route, 0) == 0]
    if missing_boxes:
        st.warning(f"Укажите количество коробок для маршрутов: {', '.join(missing_boxes)}")
        st.stop()

    for route in selected_routes:
        route_df = df[df["Номер маршрута"] == route]
        
        update_route(route, car_number, driver, plomb, boxes_input)

        pdf_file = generate_pdf(
            route_df,
            route,
            driver,
            car_number,
            plomb,
            boxes_input
        )

        with open(pdf_file, "rb") as f:
            st.download_button(
                label=f"📄 Скачать PDF {route}",
                data=f,
                file_name=pdf_file,
                mime="application/pdf",
                key=f"download_{route}"
            )

    st.success("✅ Маршруты успешно отгружены!")
    st.balloons()
    st.rerun()

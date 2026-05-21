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
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4, landscape

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

def update_route(route_name, car_number, driver, plomb):

    sheet = connect_sheet()

    data = sheet.get_all_records()

    headers = sheet.row_values(1)

    extra_columns = [
        "Номер машины",
        "Водитель",
        "№ пломбы"
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

# ---------------- PDF ----------------

def generate_pdf(df, route, driver, car, plomb):

    filename = f"{route}.pdf"

    doc = SimpleDocTemplate(
        filename,
        pagesize=landscape(A4),
        leftMargin=20,
        rightMargin=20,
        topMargin=20,
        bottomMargin=20
    )

    styles = getSampleStyleSheet()

    styleN = styles["Normal"]
    styleN.fontName = "HYSMyeongJo-Medium"
    styleN.fontSize = 9

    styleH = styles["Heading1"]
    styleH.fontName = "HYSMyeongJo-Medium"
    styleH.fontSize = 18

    elements = []

    total_boxes = int(
        df["кол-во штук в заказе"].sum()
    )

    total_points = len(df)

    # ---------------- HEADER ----------------

    title = Paragraph(
        """
        <para align=center>
        <b>МАРШРУТНЫЙ ЛИСТ</b>
        </para>
        """,
        styleH
    )

    elements.append(title)

    elements.append(Spacer(1, 15))

    info = Paragraph(
        f"""
        <b>Маршрут:</b> {route}<br/>
        <b>Дата:</b> {datetime.now().strftime("%d.%m.%Y %H:%M")}<br/>
        <b>Водитель:</b> {driver}<br/>
        <b>Номер машины:</b> {car}<br/>
        <b>№ пломбы:</b> {plomb}<br/>
        <b>Количество магазинов:</b> {total_points}<br/>
        <b>Количество коробок:</b> {total_boxes}
        """,
        styleN
    )

    elements.append(info)

    elements.append(Spacer(1, 15))

    elements.append(
        HRFlowable(width="100%")
    )

    elements.append(Spacer(1, 10))

    # ---------------- TABLE ----------------

    data = [[
        "Заказ",
        "Магазин",
        "Адрес",
        "Маршрут",
        "Пломба",
        "Выдано",
        "Получено",
        "Подпись / Печать"
    ]]

    for _, row in df.iterrows():

        data.append([
            str(row["№ заказа"]),
            str(row["Название магазина"]),
            str(row["Адрес магазина"]),
            str(row["Номер маршрута"]),
            str(plomb),
            str(row["кол-во штук в заказе"]),
            "",
            ""
        ])

    table = Table(
        data,
        colWidths=[
            90,
            140,
            220,
            130,
            80,
            70,
            70,
            130
        ]
    )

    table.setStyle(TableStyle([

        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1F2937")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),

        ('FONTNAME', (0,0), (-1,-1), 'HYSMyeongJo-Medium'),

        ('FONTSIZE', (0,0), (-1,0), 9),
        ('FONTSIZE', (0,1), (-1,-1), 8),

        ('BOTTOMPADDING', (0,0), (-1,0), 10),
        ('TOPPADDING', (0,0), (-1,0), 10),

        ('BACKGROUND', (0,1), (-1,-1), colors.white),

        ('GRID', (0,0), (-1,-1), 0.7, colors.black),

        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),

        ('ALIGN', (0,0), (-1,-1), 'CENTER'),

    ]))

    elements.append(table)

    elements.append(Spacer(1, 30))

    sign = Paragraph(
        """
        <b>Подпись водителя:</b> ________________________________<br/><br/><br/>
        <b>Подпись принимающей стороны:</b> ________________________________
        """,
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
    "Коробок",
    int(
        not_shipped["кол-во штук в заказе"].sum()
    )
)

st.divider()

# ---------------- FORM ----------------

left, right = st.columns([1, 1])

with left:

    st.subheader("🚛 Данные машины")

    car_number = st.text_input(
        "Номер машины"
    )

    driver = st.text_input(
        "Водитель"
    )

    plomb = st.text_input(
        "№ пломбы"
    )

with right:

    st.subheader("📦 Маршруты")

    routes = sorted(
        not_shipped["Номер маршрута"]
        .dropna()
        .unique()
    )

    selected_routes = st.multiselect(
        "Выберите маршруты",
        routes
    )

# ---------------- DETAILS ----------------

if selected_routes:

    st.subheader("📋 Детали маршрутов")

    details_df = not_shipped[
        not_shipped["Номер маршрута"]
        .isin(selected_routes)
    ]

    st.dataframe(
        details_df[
            [
                "№ заказа",
                "Название магазина",
                "Адрес магазина",
                "Номер маршрута",
                "кол-во штук в заказе"
            ]
        ],
        use_container_width=True,
        height=400
    )

# ---------------- SHIP BUTTON ----------------

if st.button("✅ ОТГРУЗИТЬ И СОЗДАТЬ PDF"):

    if not car_number:

        st.warning("Введите номер машины")
        st.stop()

    if not selected_routes:

        st.warning("Выберите маршрут")
        st.stop()

    for route in selected_routes:

        route_df = df[
            df["Номер маршрута"] == route
        ]

        update_route(
            route,
            car_number,
            driver,
            plomb
        )

        pdf_file = generate_pdf(
            route_df,
            route,
            driver,
            car_number,
            plomb
        )

        with open(pdf_file, "rb") as f:

            st.download_button(
                label=f"📄 Скачать PDF {route}",
                data=f,
                file_name=pdf_file,
                mime="application/pdf"
            )

    st.success("Маршруты успешно отгружены")

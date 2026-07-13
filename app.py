import streamlit as st
import pandas as pd
import gspread
from gspread.utils import rowcol_to_a1
import tempfile
import os
import time
from datetime import datetime, timedelta

from google.oauth2.service_account import Credentials

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

from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase import pdfmetrics

# ---------------- PDF FONT ----------------
# DejaVuSans нормально поддерживает кириллицу (в отличие от корейского
# CID-шрифта HYSMyeongJo-Medium, который давал огромные разрядки между
# буквами). Шрифт ставится в систему через packages.txt (fonts-dejavu).
FONT_REGULAR = "Helvetica"
FONT_BOLD = "Helvetica-Bold"

_DEJAVU_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
_DEJAVU_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

try:
    if os.path.exists(_DEJAVU_REGULAR) and os.path.exists(_DEJAVU_BOLD):
        pdfmetrics.registerFont(TTFont("DejaVuSans", _DEJAVU_REGULAR))
        pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", _DEJAVU_BOLD))
        FONT_REGULAR = "DejaVuSans"
        FONT_BOLD = "DejaVuSans-Bold"
    else:
        pdfmetrics.registerFont(UnicodeCIDFont('HYSMyeongJo-Medium'))
        FONT_REGULAR = "HYSMyeongJo-Medium"
        FONT_BOLD = "HYSMyeongJo-Medium"
    # Регистрируем семейство шрифтов, чтобы внутри Paragraph работали
    # инлайн-теги <b>...</b> (переключение на жирное начертание для
    # последних 4 цифр номера заказа), а не только фиксированный fontName.
    pdfmetrics.registerFontFamily(
        FONT_REGULAR,
        normal=FONT_REGULAR,
        bold=FONT_BOLD,
        italic=FONT_REGULAR,
        boldItalic=FONT_BOLD,
    )
except Exception:
    pass

# ---------------- PDF PALETTE ----------------
# Светло-серая палитра — оптимизирована под чёрно-белую печать
# (тёмные плашки быстро съедают картридж и дают "грязные" сканы).
PDF_ACCENT = colors.HexColor("#B0B0B0")        # светло-серый — акцент/шапки/рамки
PDF_ACCENT_LIGHT = colors.HexColor("#F2F2F2")  # почти белый фон инфо-блока
PDF_ACCENT_SOFT = colors.HexColor("#707070")   # средне-серый для подписей
PDF_BORDER = colors.HexColor("#C7C7C7")
PDF_ROW_ALT = colors.HexColor("#F7F7F7")
PDF_TEXT = colors.HexColor("#1F2937")
PDF_TEXT_MUTED = colors.HexColor("#5B6472")

# ---------------- PAGE ----------------
st.set_page_config(page_title="Отгрузка маршрутов", layout="wide")

# ---------------- SETTINGS ----------------
SHEET_ID = "1hKZ8ggNLW-OY1bV8xAW7PKl50Fof2co86oxGK92YPAA"
SHEET_NAME = "Маршруты New"

REQUIRED_EXTRA_COLUMNS = [
    "Дата отгрузки факт",
    "Номер машины",
    "Водитель",
    "№ пломбы",
    "Рейс",
]

# Инициализация session state
if 'shipment_completed' not in st.session_state:
    st.session_state.shipment_completed = False
if 'pdf_file' not in st.session_state:
    st.session_state.pdf_file = None
if 'selected_routes' not in st.session_state:
    st.session_state.selected_routes = []
if 'rollback_mode' not in st.session_state:
    st.session_state.rollback_mode = False

# ---------------- CSS ----------------
st.markdown("""
<style>
.main { background-color: #F4F6FA; }

h1 {
    color: #1E293B;
    font-weight: 800;
    letter-spacing: -0.5px;
    padding-bottom: 10px;
    border-bottom: 3px solid #2C5282;
    display: inline-block;
}

h2, h3 { color: #1E293B; font-weight: 700; }

div[data-testid="metric-container"] {
    background: white;
    border-radius: 18px;
    padding: 22px 20px;
    border: 1px solid #E5E9F2;
    border-left: 5px solid #2C5282;
    box-shadow: 0 4px 16px rgba(30, 41, 59, 0.06);
}

div[data-testid="stMetricLabel"] {
    color: #64748B;
    font-weight: 600;
}

div[data-testid="stMetricValue"] {
    color: #1E293B;
    font-weight: 800;
}

div[data-testid="stExpander"] {
    background: white;
    border-radius: 16px;
    border: 1px solid #E5E9F2;
    border-left: 5px solid #0F766E;
    box-shadow: 0 2px 10px rgba(30, 41, 59, 0.04);
}

.stButton>button {
    background: linear-gradient(135deg, #1E3A5F 0%, #2C5282 100%);
    color: white;
    border-radius: 12px;
    border: none;
    padding: 14px 22px;
    font-weight: 700;
    width: 100%;
    font-size: 16px;
    transition: all 0.15s ease;
    box-shadow: 0 2px 8px rgba(30, 58, 95, 0.25);
}
.stButton>button:hover {
    background: linear-gradient(135deg, #16304E 0%, #244873 100%);
    box-shadow: 0 4px 12px rgba(30, 58, 95, 0.35);
}

div[data-testid="stDownloadButton"] > button {
    background: linear-gradient(135deg, #0F766E 0%, #14958A 100%);
    color: white;
    border-radius: 12px;
    border: none;
    padding: 14px 22px;
    font-weight: 700;
    width: 100%;
    font-size: 16px;
    box-shadow: 0 2px 8px rgba(15, 118, 110, 0.25);
}
div[data-testid="stDownloadButton"] > button:hover {
    background: linear-gradient(135deg, #0B5F58 0%, #107D74 100%);
}

.stButton > button[kind="secondary"] {
    background: linear-gradient(135deg, #B91C1C 0%, #DC2626 100%);
    box-shadow: 0 2px 8px rgba(185, 28, 28, 0.25);
}
.stButton > button[kind="secondary"]:hover {
    background: linear-gradient(135deg, #991717 0%, #C31F1F 100%);
}

div[data-testid="stDataFrame"] {
    border-radius: 14px;
    overflow: hidden;
    border: 1px solid #E5E9F2;
}

div[data-testid="stTextInput"] > div {
    border-radius: 10px;
}

div[data-testid="stTextInput"] input {
    border: 1.5px solid #CBD5E1;
    border-radius: 10px;
}

hr { border-color: #E2E8F0 !important; }
</style>
""", unsafe_allow_html=True)

# ---------------- GOOGLE SHEETS ----------------
def connect_sheet():
    try:
        if "gcp_service_account" not in st.secrets:
            st.error("gcp_service_account не найден в secrets!")
            return None

        creds_dict = dict(st.secrets["gcp_service_account"])
        if 'private_key' in creds_dict:
            creds_dict['private_key'] = creds_dict['private_key'].replace('\\n', '\n')

        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        credentials = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(credentials)
        sheet = client.open_by_key(SHEET_ID).worksheet(SHEET_NAME)
        return sheet
    except Exception as e:
        st.error(f"Ошибка подключения: {str(e)}")
        return None


def get_data():
    sheet = connect_sheet()
    if sheet is None:
        return pd.DataFrame()
    try:
        data = sheet.get_all_records()
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Ошибка чтения: {str(e)}")
        return pd.DataFrame()


def ensure_required_columns(sheet, headers):
    """
    Проверяет, что все нужные колонки существуют в шапке таблицы.
    Если каких-то не хватает — добавляет их В КОНЕЦ и ПРОПИСЫВАЕТ заголовки
    (раньше здесь был баг: колонки добавлялись пустыми, без названия,
    из-за чего headers.index(...) сразу падал с ValueError).
    Возвращает актуальный список headers.
    """
    missing = [col for col in REQUIRED_EXTRA_COLUMNS if col not in headers]
    if not missing:
        return headers

    start_col = len(headers) + 1  # 1-based
    sheet.add_cols(len(missing))

    header_updates = []
    for i, col_name in enumerate(missing):
        col_num = start_col + i
        header_updates.append({
            'range': rowcol_to_a1(1, col_num),
            'values': [[col_name]]
        })
    sheet.batch_update([{'range': u['range'], 'values': u['values']} for u in header_updates])

    return headers + missing


def get_required_col_indices(headers, names):
    """
    Безопасно находит индексы нужных колонок.
    Если какой-то колонки нет — кидает понятное исключение,
    вместо невнятного ValueError из headers.index(...).
    """
    result = {}
    missing = []
    for key, col_name in names.items():
        if col_name in headers:
            result[key] = headers.index(col_name)
        else:
            missing.append(col_name)
    if missing:
        raise ValueError(f"В таблице не найдены колонки: {', '.join(missing)}")
    return result


def update_routes_batch(routes_list, car_number, driver, plomb, trip_number):
    sheet = connect_sheet()
    if sheet is None:
        return False

    try:
        all_data = sheet.get_all_values()
        headers = all_data[0]

        # Гарантируем наличие всех нужных колонок (с заголовками!)
        headers = ensure_required_columns(sheet, headers)
        if headers != all_data[0]:
            all_data = sheet.get_all_values()
            headers = all_data[0]

        col_indices = get_required_col_indices(headers, {
            'status': "Статус отгрузки",
            'route': "Номер маршрута",
            'fact': "Дата отгрузки факт",
            'car': "Номер машины",
            'driver': "Водитель",
            'plomb': "№ пломбы",
            'trip': "Рейс",
        })

        now_utc_plus_5 = datetime.now() + timedelta(hours=5)
        fact_date = now_utc_plus_5.strftime("%d.%m.%Y %H:%M")

        updates = []
        route_indices = [str(r) for r in routes_list]

        for idx, row in enumerate(all_data[1:], start=2):
            if len(row) > col_indices['route'] and str(row[col_indices['route']]) in route_indices:
                updates.append({'range': rowcol_to_a1(idx, col_indices["status"] + 1), 'value': "ОТГРУЖЕН"})
                updates.append({'range': rowcol_to_a1(idx, col_indices["fact"] + 1), 'value': fact_date})
                updates.append({'range': rowcol_to_a1(idx, col_indices["car"] + 1), 'value': car_number})
                updates.append({'range': rowcol_to_a1(idx, col_indices["driver"] + 1), 'value': driver})
                updates.append({'range': rowcol_to_a1(idx, col_indices["plomb"] + 1), 'value': plomb})
                updates.append({'range': rowcol_to_a1(idx, col_indices["trip"] + 1), 'value': trip_number})

        if updates:
            batch = []
            for i, update in enumerate(updates):
                batch.append(update)
                if len(batch) >= 50 or i == len(updates) - 1:
                    sheet.batch_update([{'range': u['range'], 'values': [[u['value']]]} for u in batch])
                    batch = []
                    time.sleep(0.5)

        return True

    except Exception as e:
        st.error(f"Ошибка обновления: {str(e)}")
        return False


def rollback_routes_batch(routes_list):
    sheet = connect_sheet()
    if sheet is None:
        return False

    try:
        all_data = sheet.get_all_values()
        headers = all_data[0]

        col_indices = get_required_col_indices(headers, {
            'status': "Статус отгрузки",
            'route': "Номер маршрута",
            'fact': "Дата отгрузки факт",
            'car': "Номер машины",
            'driver': "Водитель",
            'plomb': "№ пломбы",
            'trip': "Рейс",
        })

        updates = []
        route_strs = [str(r) for r in routes_list]

        for idx, row in enumerate(all_data[1:], start=2):
            if len(row) > col_indices['route'] and str(row[col_indices['route']]) in route_strs:
                updates.append({'range': rowcol_to_a1(idx, col_indices["status"] + 1), 'value': ""})
                updates.append({'range': rowcol_to_a1(idx, col_indices["fact"] + 1), 'value': ""})
                updates.append({'range': rowcol_to_a1(idx, col_indices["car"] + 1), 'value': ""})
                updates.append({'range': rowcol_to_a1(idx, col_indices["driver"] + 1), 'value': ""})
                updates.append({'range': rowcol_to_a1(idx, col_indices["plomb"] + 1), 'value': ""})
                updates.append({'range': rowcol_to_a1(idx, col_indices["trip"] + 1), 'value': ""})

        if updates:
            batch = []
            for i, update in enumerate(updates):
                batch.append(update)
                if len(batch) >= 50 or i == len(updates) - 1:
                    sheet.batch_update([{'range': u['range'], 'values': [[u['value']]]} for u in batch])
                    batch = []
                    time.sleep(0.5)

        return True

    except Exception as e:
        st.error(f"Ошибка отката: {str(e)}")
        return False


# ---------------- PDF GENERATION ----------------
def generate_delivery_pdf(all_data, routes_list, driver, car, plomb, trip_number):
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
        filename = tmp_file.name

    # Поля увеличены до 10мм — у большинства принтеров край листа
    # физически непечатаемый (обычно 3-5мм), и старые поля в 8мм вкупе
    # с шириной таблицы ровно "в притык" к листу приводили к обрезке
    # правого края (столбца "Подпись водителя") при печати.
    PAGE_MARGIN = 10 * mm
    doc = SimpleDocTemplate(
        filename,
        pagesize=landscape(A4),
        leftMargin=PAGE_MARGIN,
        rightMargin=PAGE_MARGIN,
        topMargin=8 * mm,
        bottomMargin=10 * mm
    )

    # Реальная печатная область landscape A4: 297мм - 2*10мм = 277мм.
    # Берём с запасом 268мм, чтобы гарантированно ничего не обрезалось
    # на реальном принтере (не полагаемся на "ровно по линейке").
    CONTENT_WIDTH = 268 * mm

    styles = getSampleStyleSheet()

    # Шрифты уменьшены по всему шаблону
    styleTitle = ParagraphStyle(
        'CustomTitle',
        parent=styles['Normal'],
        fontName=FONT_BOLD,
        fontSize=13,
        leading=16,
        alignment=1,
        textColor=PDF_TEXT,
    )

    styleInfoLabel = ParagraphStyle(
        'CustomInfoLabel',
        parent=styles['Normal'],
        fontName=FONT_BOLD,
        fontSize=9,
        leading=12,
        spaceAfter=2,
        textColor=PDF_ACCENT_SOFT
    )

    styleInfoValue = ParagraphStyle(
        'CustomInfoValue',
        parent=styles['Normal'],
        fontName=FONT_BOLD,
        fontSize=11.5,
        leading=15,
        spaceAfter=3,
        textColor=PDF_TEXT
    )

    styleCell = ParagraphStyle(
        'CustomCell',
        parent=styles['Normal'],
        fontName=FONT_REGULAR,
        fontSize=9,
        leading=12,
        textColor=PDF_TEXT
    )

    # Стиль номера заказа: базовое начертание обычное, а последние 4 цифры
    # выделяются тегом <b>...</b> прямо в тексте — работает благодаря
    # registerFontFamily() у DejaVuSans выше.
    styleOrderNum = ParagraphStyle(
        'CustomOrderNum',
        parent=styles['Normal'],
        fontName=FONT_REGULAR,
        fontSize=9.5,
        leading=12,
        textColor=PDF_TEXT
    )

    styleHeader = ParagraphStyle(
        'CustomHeader',
        parent=styles['Normal'],
        fontName=FONT_BOLD,
        fontSize=8.5,
        leading=11,
        alignment=1,
        textColor=PDF_TEXT
    )

    styleSignature = ParagraphStyle(
        'CustomSignature',
        parent=styles['Normal'],
        fontName=FONT_REGULAR,
        fontSize=10,
        leading=13,
        textColor=PDF_TEXT_MUTED
    )

    elements = []
    total_points = len(all_data)

    # ===== ЗАГОЛОВОК В ПЛАШКЕ =====
    title_table = Table(
        [[Paragraph("МАРШРУТНЫЙ ЛИСТ ДОСТАВКИ", styleTitle)]],
        colWidths=[CONTENT_WIDTH]
    )
    title_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), PDF_ACCENT),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('ROUNDEDCORNERS', [8, 8, 8, 8]),
    ]))
    elements.append(title_table)
    elements.append(Spacer(1, 8))

    # ===== ИНФО-БЛОК =====
    info_row1 = [
        Paragraph("РЕЙС", styleInfoLabel),
        Paragraph(f"{trip_number}", styleInfoValue),
        Paragraph("МАШИНА", styleInfoLabel),
        Paragraph(f"{car}", styleInfoValue),
        Paragraph("ВСЕГО ЗАКАЗОВ", styleInfoLabel),
        Paragraph(f"{total_points}", styleInfoValue)
    ]
    info_row2 = [
        Paragraph("ВОДИТЕЛЬ", styleInfoLabel),
        Paragraph(f"{driver}", styleInfoValue),
        Paragraph("ПЛОМБА", styleInfoLabel),
        # Значение пломбы растянуто через SPAN на оставшиеся колонки —
        # ложится горизонтально, а не переносится вертикально по строкам.
        Paragraph(f"{plomb}", styleInfoValue),
        Paragraph("", styleInfoLabel),
        Paragraph("", styleInfoValue)
    ]

    info_col_widths = [34 * mm, 58 * mm, 36 * mm, 58 * mm, 48 * mm, 24 * mm]  # сумма = 258... см. ниже
    # корректируем последнюю колонку так, чтобы сумма точно равнялась CONTENT_WIDTH
    diff = CONTENT_WIDTH - sum(info_col_widths)
    info_col_widths[-1] = info_col_widths[-1] + diff

    info_table = Table(
        [info_row1, info_row2],
        colWidths=info_col_widths
    )
    info_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BACKGROUND', (0, 0), (-1, -1), PDF_ACCENT_LIGHT),
        ('LEFTPADDING', (0, 0), (-1, -1), 9),
        ('RIGHTPADDING', (0, 0), (-1, -1), 9),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('LINEBELOW', (0, 0), (-1, 0), 0.6, PDF_BORDER),
        ('SPAN', (3, 1), (5, 1)),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 4))
    elements.append(HRFlowable(width="100%", thickness=1.3, color=PDF_ACCENT))
    elements.append(Spacer(1, 10))

    # ===== ТАБЛИЦА С ЗАКАЗАМИ =====
    headers = [
        "№ заказа",
        "Магазин",
        "Адрес",
        "Пломба",
        "Выдано<br/>коробок",
        "Получено<br/>коробок",
        "Выданы<br/>пустые<br/>коробки",
        "Подпись, печать,<br/>комментарии",
        "Подпись<br/>водителя"
    ]
    table_data = [[Paragraph(h, styleHeader) for h in headers]]

    for _, row in all_data.iterrows():
        order_num_full = str(row.get('№ заказа', ''))
        # Последние 4 символа номера заказа выделяем жирным — это то,
        # что чаще всего отличает заказы друг от друга на листе, легче
        # находить взглядом.
        if len(order_num_full) > 4:
            order_num_html = f"{order_num_full[:-4]}<b>{order_num_full[-4:]}</b>"
        else:
            order_num_html = f"<b>{order_num_full}</b>"

        shop_name = str(row.get("Название магазина", ""))[:50]
        address = str(row.get("Адрес магазина", ""))[:70]

        table_data.append([
            Paragraph(order_num_html, styleOrderNum),
            Paragraph(shop_name, styleCell),
            Paragraph(address, styleCell),
            Paragraph(" ", styleCell),
            Paragraph(" ", styleCell),
            Paragraph(" ", styleCell),
            Paragraph(" ", styleCell),
            Paragraph(" ", styleCell),
            Paragraph(" ", styleCell)
        ])

    table_col_widths = [20 * mm, 33 * mm, 57 * mm, 19 * mm, 21 * mm, 21 * mm, 23 * mm, 44 * mm, 28 * mm]
    diff_t = CONTENT_WIDTH - sum(table_col_widths)
    table_col_widths[2] = table_col_widths[2] + diff_t  # добавляем/убираем разницу в "Адрес"

    table = Table(
        table_data,
        colWidths=table_col_widths,
        repeatRows=1
    )

    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), PDF_ACCENT),
        ('TEXTCOLOR', (0, 0), (-1, 0), PDF_TEXT),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, PDF_ROW_ALT]),
        ('VALIGN', (0, 1), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.6, PDF_BORDER),
        ('BOX', (0, 0), (-1, -1), 1, PDF_ACCENT),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('ALIGN', (0, 1), (0, -1), 'CENTER'),
        ('ALIGN', (1, 1), (2, -1), 'LEFT'),
        ('ALIGN', (3, 1), (-1, -1), 'CENTER'),
    ]))

    elements.append(table)
    elements.append(Spacer(1, 18))

    # ===== ПОДПИСИ =====
    sig_data = [
        [Paragraph("Подпись водителя: _________________________", styleSignature),
         Paragraph("Подпись ответственного: _________________________", styleSignature)]
    ]
    sig_table = Table(sig_data, colWidths=[CONTENT_WIDTH / 2, CONTENT_WIDTH / 2])
    sig_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    elements.append(sig_table)

    doc.build(elements)
    return filename


# ---------------- MAIN ----------------
st.title("Система отгрузки маршрутов")

with st.spinner("Загрузка данных..."):
    df = get_data()

if df.empty:
    st.error("Нет данных")
    st.stop()

if "Статус отгрузки" not in df.columns:
    st.error('В таблице отсутствует колонка "Статус отгрузки". Проверьте название колонки в Google Sheets.')
    st.stop()

if "Номер маршрута" not in df.columns:
    st.error('В таблице отсутствует колонка "Номер маршрута". Проверьте название колонки в Google Sheets.')
    st.stop()

not_shipped = df[df["Статус отгрузки"] != "ОТГРУЖЕН"]
shipped = df[df["Статус отгрузки"] == "ОТГРУЖЕН"]

col1, col2, col3, col4 = st.columns(4)
col1.metric("Не отгружено", not_shipped["Номер маршрута"].nunique())
col2.metric("Отгружено", shipped["Номер маршрута"].nunique())
col3.metric("Точек", len(not_shipped))
col4.metric(
    "Кол-во шт",
    int(not_shipped["кол-во штук в заказе"].sum())
    if "кол-во штук в заказе" in not_shipped.columns and not not_shipped.empty else 0
)

st.divider()

# ==================== СВОДНОЕ ОКНО СВЕРХУ ====================
if not not_shipped.empty and "Название магазина" in not_shipped.columns and "Адрес магазина" in not_shipped.columns:
    with st.expander("Сводная информация по магазинам (без группировки по заказам)", expanded=False):
        st.markdown("### Сводка по магазинам и адресам")

        agg_dict = {"№ заказа": "count"}
        if "кол-во штук в заказе" in not_shipped.columns:
            agg_dict["кол-во штук в заказе"] = "sum"

        summary_by_shop = not_shipped.groupby(["Название магазина", "Адрес магазина"]).agg(agg_dict)
        rename_map = {"№ заказа": "Кол-во заказов"}
        if "кол-во штук в заказе" in agg_dict:
            rename_map["кол-во штук в заказе"] = "Всего штук"
        summary_by_shop = summary_by_shop.rename(columns=rename_map).reset_index()

        sort_col = "Всего штук" if "Всего штук" in summary_by_shop.columns else "Кол-во заказов"
        summary_by_shop = summary_by_shop.sort_values(sort_col, ascending=False)

        # Пересобираем через обычные python-типы — защита от краша st.dataframe
        # на несовместимых arrow-backed dtypes (известная проблема pandas 3.x).
        summary_by_shop_display = pd.DataFrame(summary_by_shop.to_dict('records'))

        st.dataframe(
            summary_by_shop_display,
            width='stretch',
            hide_index=True
        )

        total_shops = len(summary_by_shop)
        total_orders_all = summary_by_shop["Кол-во заказов"].sum()

        col_a, col_b, col_c = st.columns(3)
        col_a.metric("Уникальных магазинов", total_shops)
        if "Всего штук" in summary_by_shop.columns:
            col_b.metric("Всего штук", int(summary_by_shop["Всего штук"].sum()))
        col_c.metric("Всего заказов", int(total_orders_all))

        st.markdown("---")

        st.markdown("### Детальный список по магазинам")
        for idx, row in summary_by_shop.iterrows():
            with st.container():
                qty_txt = f"{int(row['Всего штук'])} шт. | " if "Всего штук" in summary_by_shop.columns else ""
                st.markdown(f"""
                **{row['Название магазина']}**  
                *{row['Адрес магазина']}*  
                {qty_txt}{int(row['Кол-во заказов'])} заказ(ов)
                """)
                st.divider()

st.divider()

# ==================== ОСНОВНОЙ ИНТЕРФЕЙС ====================
if st.button("Откатить маршруты", type="secondary"):
    st.session_state.rollback_mode = True
    st.rerun()

if st.session_state.get('rollback_mode', False):
    st.subheader("Режим отката")
    shipped_routes = shipped[shipped["Статус отгрузки"] == "ОТГРУЖЕН"]

    if len(shipped_routes) > 0:
        routes_for_rollback = sorted(shipped_routes["Номер маршрута"].dropna().unique())
        routes_to_rollback = st.multiselect("Выберите маршруты для отката", options=routes_for_rollback)

        col1, col2 = st.columns(2)
        if col1.button("Подтвердить откат"):
            if routes_to_rollback and rollback_routes_batch(routes_to_rollback):
                st.success(f"Откачено {len(routes_to_rollback)} маршрутов")
                st.session_state.rollback_mode = False
                time.sleep(1)
                st.rerun()
        if col2.button("Отмена"):
            st.session_state.rollback_mode = False
            st.rerun()
    else:
        st.info("Нет отгруженных маршрутов")
        if st.button("Назад"):
            st.session_state.rollback_mode = False
            st.rerun()

elif not st.session_state.get('shipment_completed', False):
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Данные")
        car_number = st.text_input("Номер машины")
        driver = st.text_input("Водитель")
        plomb = st.text_input("№ пломбы")
        trip_number = st.text_input("Рейс")

    with col2:
        st.subheader("Маршруты")
        if not not_shipped.empty:
            routes = sorted(not_shipped["Номер маршрута"].dropna().unique())
            selected_routes = st.multiselect("Выберите маршруты", routes)
        else:
            selected_routes = []

    if selected_routes:
        st.subheader("Детали выбранных маршрутов")
        details = not_shipped[not_shipped["Номер маршрута"].isin(selected_routes)]

        display_cols = ["№ заказа", "Название магазина", "Адрес магазина", "кол-во штук в заказе", "Номер маршрута"]
        available_cols = [col for col in display_cols if col in details.columns]

        details_display = pd.DataFrame(details[available_cols].to_dict('records'))

        st.dataframe(
            details_display,
            width='stretch',
            column_config={
                "кол-во штук в заказе": st.column_config.NumberColumn("Кол-во шт", format="%d"),
                "№ заказа": "№ заказа",
                "Название магазина": "Магазин",
                "Адрес магазина": "Адрес",
                "Номер маршрута": "Маршрут"
            }
        )

        total_orders = len(details)
        total_quantity = details["кол-во штук в заказе"].sum() if "кол-во штук в заказе" in details.columns else 0
        st.info(f"Итого: {total_orders} заказов, {int(total_quantity)} штук")

    if st.button("ОТГРУЗИТЬ", type="primary"):
        if not all([car_number, driver, plomb, trip_number, selected_routes]):
            st.warning("Заполните все поля и выберите маршруты")
        else:
            with st.spinner("Создание PDF и отгрузка..."):
                data_for_pdf = not_shipped[not_shipped["Номер маршрута"].isin(selected_routes)]
                if update_routes_batch(selected_routes, car_number, driver, plomb, trip_number):
                    pdf_file = generate_delivery_pdf(data_for_pdf, selected_routes, driver, car_number, plomb, trip_number)
                    st.session_state.pdf_file = pdf_file
                    st.session_state.shipment_completed = True
                    st.session_state.selected_routes = selected_routes
                    st.rerun()

elif st.session_state.get('shipment_completed') and st.session_state.get('pdf_file'):
    st.success(f"Отгружены маршруты: {', '.join(str(r) for r in st.session_state.selected_routes)}")

    if os.path.exists(st.session_state.pdf_file):
        with open(st.session_state.pdf_file, "rb") as f:
            st.download_button("Скачать PDF", f, file_name=f"route_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf", mime="application/pdf")

    if st.button("Новая отгрузка"):
        try:
            if st.session_state.pdf_file and os.path.exists(st.session_state.pdf_file):
                os.unlink(st.session_state.pdf_file)
        except Exception:
            pass
        st.session_state.shipment_completed = False
        st.session_state.pdf_file = None
        st.session_state.selected_routes = []
        st.rerun()

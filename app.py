from __future__ import annotations

from datetime import date, datetime
import hmac

import pandas as pd
import plotly.express as px
import streamlit as st

import database as db
from calculations import (
    calculate_net_worth,
    debt_to_income_ratio,
    etf_allocation,
    financial_score,
    monthly_decision,
    payoff_priority,
)
from ui_components import (
    alert,
    empty_state,
    format_try,
    format_usd,
    inject_css,
    line_chart,
    metric_card,
    monthly_bar_chart,
    page_header,
)


st.set_page_config(
    page_title="Project Atlas",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="expanded",
)


def require_password() -> None:
    """Protect cloud deployments when APP_PASSWORD is configured."""
    try:
        configured_password = st.secrets.get("APP_PASSWORD", "")
    except st.errors.StreamlitSecretNotFoundError:
        configured_password = ""
    if not configured_password:
        return

    if st.session_state.get("atlas_authenticated"):
        return

    st.markdown(
        """
        <div style="max-width:520px;margin:9vh auto 1rem;padding:2rem;border:1px solid #e2e8f0;
        border-radius:20px;background:white;box-shadow:0 16px 45px rgba(15,23,42,.10)">
          <h1 style="margin:0">🧭 Project Atlas</h1>
          <p style="color:#64748b">Kişisel finans paneline erişmek için parolanızı girin.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    password = st.text_input("Uygulama parolası", type="password")
    if st.button("Giriş Yap", width="stretch"):
        entered_password = password.strip()
        expected_password = str(configured_password).strip()
        if hmac.compare_digest(entered_password, expected_password):
            st.session_state["atlas_authenticated"] = True
            st.rerun()
        else:
            st.error("Parola yanlış.")
    st.stop()


require_password()
db.init_db()
inject_css()


EXPENSE_CATEGORIES = [
    "Kira",
    "Elektrik",
    "Su",
    "Jeotermal",
    "Telefon",
    "İnternet",
    "Market / Yeme-İçme",
    "Kıyafet",
    "Sosyal Hayat",
    "Beklenmedik Gider",
]

PAGES = [
    "Ana Sayfa",
    "Gelir Girişi",
    "Gider Girişi",
    "Kredi Kartı Borç Merkezi",
    "Aylık Karar Motoru",
    "Midas ETF Planı",
    "Hedefler",
    "Raporlar",
]


def latest_monthly_income() -> float:
    frame = db.query_df(
        """
        SELECT COALESCE(SUM(amount), 0) AS value
        FROM incomes
        WHERE substr(income_date, 1, 7) = (
            SELECT MAX(substr(income_date, 1, 7)) FROM incomes
        )
        """
    )
    return float(frame.iloc[0]["value"] or 0)


def emergency_fund_value() -> float:
    frame = db.query_df(
        "SELECT current_amount FROM goals WHERE name = 'Acil durum fonu'"
    )
    return float(frame.iloc[0]["current_amount"]) if not frame.empty else 0


def financial_overview() -> dict[str, float]:
    now = date.today()
    income, expenses = db.get_month_totals(now.year, now.month)
    cash = db.get_cash()
    debt = db.get_total_debt()
    investment = db.get_investment_value()
    return {
        "cash": cash,
        "debt": debt,
        "investment": investment,
        "net_worth": calculate_net_worth(cash, investment, debt),
        "income": income,
        "expenses": expenses,
        "reference_income": income or latest_monthly_income(),
    }


def render_sidebar() -> str:
    with st.sidebar:
        st.markdown("## 🧭 Project Atlas")
        st.caption("Kişisel finans kontrol merkezi")
        page = st.radio("Menü", PAGES, label_visibility="collapsed")
        st.divider()
        overview = financial_overview()
        st.caption("Güncel nakit")
        st.markdown(f"### {format_try(overview['cash'])}")
        st.caption(f"Toplam borç: {format_try(overview['debt'])}")
        with st.expander("Nakdi manuel düzelt"):
            cash_value = st.number_input(
                "Güncel nakit (TL)",
                min_value=0.0,
                value=float(overview["cash"]),
                step=500.0,
                key="sidebar_cash",
            )
            if st.button("Nakdi güncelle", width="stretch"):
                db.set_cash(cash_value)
                st.success("Nakit güncellendi.")
                st.rerun()
        st.caption("Veriler yerel atlas.db dosyasında saklanır.")
    return page


def render_home() -> None:
    page_header("Project Atlas", "Paranı gör, önceliğini seç, rotanı koru.")
    data = financial_overview()
    emergency = emergency_fund_value()
    score, reasons = financial_score(
        net_worth=data["net_worth"],
        total_debt=data["debt"],
        monthly_income=data["reference_income"],
        minimum_payment_habit=db.has_minimum_payment_habit(),
        emergency_fund=emergency,
        regular_investment=db.has_regular_investment(),
    )
    debt_ratio = debt_to_income_ratio(data["debt"], data["reference_income"])
    can_invest = data["debt"] <= 0 and data["net_worth"] >= 0

    cols = st.columns(5)
    with cols[0]:
        metric_card("Toplam Nakit", format_try(data["cash"]), "Kullanılabilir bakiye", "good")
    with cols[1]:
        metric_card(
            "Kart Borcu",
            format_try(data["debt"]),
            "Tüm kartlar",
            "risk" if data["debt"] > 0 else "good",
        )
    with cols[2]:
        metric_card(
            "Net Servet",
            format_try(data["net_worth"]),
            "Nakit + yatırım - borç",
            "good" if data["net_worth"] >= 0 else "risk",
        )
    with cols[3]:
        metric_card(
            "Yatırım Kararı",
            "Uygun" if can_invest else "Bekle",
            "Borç bitmeden agresif yatırım yok",
            "good" if can_invest else "warning",
        )
    with cols[4]:
        metric_card(
            "Finansal Skor",
            f"{score}/100",
            "Mevcut finansal dayanıklılık",
            "good" if score >= 75 else "warning" if score >= 50 else "risk",
        )

    if data["debt"] > 0:
        alert("Bu ay yatırım yapma, önce kredi kartı borcunu azalt.", "risk")
    else:
        alert("Bu ay yatırım yapılabilir.", "good")

    left, right = st.columns([1.25, 1])
    with left:
        st.subheader("Bu ayın görünümü")
        decision = monthly_decision(
            income=data["income"],
            expenses=data["expenses"],
            total_debt=data["debt"],
            current_emergency_fund=emergency,
            net_worth=data["net_worth"],
        )
        month_cols = st.columns(3)
        with month_cols[0]:
            metric_card("Gelir", format_try(data["income"]), date.today().strftime("%m/%Y"), "good")
        with month_cols[1]:
            metric_card("Gider", format_try(data["expenses"]), date.today().strftime("%m/%Y"), "warning")
        with month_cols[2]:
            metric_card(
                "Kalan",
                format_try(decision.remaining_money),
                "Gelir - gider",
                "good" if decision.remaining_money > 0 else "risk",
            )
        st.caption(
            "Maaş günü sabit olmadığı için karar motoru yalnızca seçili ayda kaydedilen "
            "gerçekleşmiş gelir ve giderleri kullanır."
        )
    with right:
        st.subheader("Risk göstergeleri")
        st.progress(min(score / 100, 1), text=f"Finansal skor: {score}/100")
        ratio_text = "Hesaplanamıyor" if debt_ratio == float("inf") else f"%{debt_ratio * 100:.1f}"
        st.write(f"**Borç / referans aylık gelir:** {ratio_text}")
        if debt_ratio > 0.30:
            st.error("Yüksek risk: Kart borcu aylık gelirin %30'unu aşıyor.")
        with st.expander("Skorun ayrıntıları"):
            if reasons:
                for reason in reasons:
                    st.write(f"• {reason}")
            else:
                st.write("Puan kesintisi bulunmuyor.")


def render_income() -> None:
    page_header("Gelir Girişi", "Maaş ve ek gelirlerini gerçekleştiği tarihte kaydet.")
    with st.form("income_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            income_type = st.selectbox("Gelir türü", ["Maaş", "Ek Gelir", "Prim", "Diğer"])
            amount = st.number_input("Tutar (TL)", min_value=0.0, step=500.0)
        with c2:
            income_date = st.date_input("Gelir tarihi", value=date.today())
            update_cash = st.checkbox("Tutarı güncel nakde ekle", value=True)
        description = st.text_input("Açıklama")
        submitted = st.form_submit_button("Geliri Kaydet", width="stretch")
        if submitted:
            if amount <= 0:
                st.error("Lütfen sıfırdan büyük bir gelir tutarı girin.")
            else:
                db.add_income(amount, income_date, income_type, description, update_cash)
                st.success("Gelir kaydedildi.")

    st.subheader("Son gelir kayıtları")
    frame = db.query_df(
        """
        SELECT income_date AS Tarih, income_type AS Tür, amount AS Tutar, description AS Açıklama
        FROM incomes ORDER BY income_date DESC, id DESC LIMIT 20
        """
    )
    st.dataframe(
        frame,
        width="stretch",
        hide_index=True,
        column_config={"Tutar": st.column_config.NumberColumn(format="%.2f TL")},
    )


def render_expense() -> None:
    page_header("Gider Girişi", "Sabit ve değişken harcamalarını tek yerde izle.")
    with st.form("expense_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            category = st.selectbox("Gider kategorisi", EXPENSE_CATEGORIES)
            amount = st.number_input("Tutar (TL)", min_value=0.0, step=100.0)
        with c2:
            expense_date = st.date_input("Gider tarihi", value=date.today())
            update_cash = st.checkbox("Tutarı güncel nakitten düş", value=True)
        description = st.text_input("Açıklama")
        submitted = st.form_submit_button("Gideri Kaydet", width="stretch")
        if submitted:
            if amount <= 0:
                st.error("Lütfen sıfırdan büyük bir gider tutarı girin.")
            else:
                db.add_expense(category, amount, expense_date, description, update_cash)
                st.success("Gider kaydedildi.")

    st.subheader("Son gider kayıtları")
    frame = db.query_df(
        """
        SELECT expense_date AS Tarih, category AS Kategori, amount AS Tutar, description AS Açıklama
        FROM expenses ORDER BY expense_date DESC, id DESC LIMIT 20
        """
    )
    st.dataframe(
        frame,
        width="stretch",
        hide_index=True,
        column_config={"Tutar": st.column_config.NumberColumn(format="%.2f TL")},
    )


def render_debt_center() -> None:
    page_header("Kredi Kartı Borç Merkezi", "Küçük borçları kapat, sonra ana borca yüklen.")
    cards = db.query_df("SELECT * FROM credit_cards ORDER BY total_debt ASC")
    names = cards["name"].tolist() if not cards.empty else []
    selection = st.selectbox("Düzenlenecek kart", names + ["Yeni kart"])
    selected = (
        cards[cards["name"] == selection].iloc[0] if selection in names else None
    )

    with st.form("card_form"):
        c1, c2 = st.columns(2)
        with c1:
            card_name = st.text_input(
                "Kart adı", value=str(selected["name"]) if selected is not None else ""
            )
            total_debt = st.number_input(
                "Toplam borç (TL)",
                min_value=0.0,
                value=float(selected["total_debt"]) if selected is not None else 0.0,
                step=100.0,
            )
            minimum = st.number_input(
                "Asgari ödeme (TL)",
                min_value=0.0,
                value=float(selected["minimum_payment"]) if selected is not None else 0.0,
                step=100.0,
            )
        with c2:
            due_default = date.today()
            if selected is not None and selected["due_date"]:
                due_default = datetime.strptime(str(selected["due_date"]), "%Y-%m-%d").date()
            due_date = st.date_input("Son ödeme tarihi", value=due_default)
            paid_amount = st.number_input("Şimdi ödenen tutar (TL)", min_value=0.0, step=100.0)
            payment_date = st.date_input("Ödeme tarihi", value=date.today())
            update_cash = st.checkbox("Ödemeyi güncel nakitten düş", value=True)
        notes = st.text_input("Ödeme açıklaması")
        submitted = st.form_submit_button("Kart Bilgilerini Kaydet", width="stretch")
        if submitted:
            if not card_name.strip():
                st.error("Kart adı boş bırakılamaz.")
            elif paid_amount > total_debt:
                st.error("Ödenen tutar toplam borçtan büyük olamaz.")
            else:
                card_id = db.upsert_credit_card(card_name.strip(), total_debt, minimum, due_date)
                db.add_card_payment(card_id, paid_amount, payment_date, notes, update_cash)
                st.success("Kart bilgileri kaydedildi.")
                st.rerun()

    cards = db.query_df(
        """
        SELECT id, name AS Kart, total_debt AS Kalan_Borç,
               minimum_payment AS Asgari_Ödeme, due_date AS Son_Ödeme
        FROM credit_cards ORDER BY total_debt ASC
        """
    )
    total = float(cards["Kalan_Borç"].sum()) if not cards.empty else 0
    c1, c2 = st.columns([1, 1.4])
    with c1:
        st.subheader("Borç kapatma önceliği")
        priority = payoff_priority(
            [
                {"name": row["Kart"], "total_debt": row["Kalan_Borç"]}
                for _, row in cards.iterrows()
            ]
        )
        if priority:
            for index, card in enumerate(priority, 1):
                st.write(f"**{index}. {card['name']}** — {format_try(card['total_debt'])}")
        else:
            alert("Tebrikler, kredi kartı borcu kalmadı.", "good")
        st.caption("Önce küçük borçlar; ardından Ziraat ana borcu.")
    with c2:
        fig = px.bar(
            cards,
            x="Kart",
            y="Kalan_Borç",
            title=f"Toplam Borç: {format_try(total)}",
            color="Kalan_Borç",
            color_continuous_scale=["#f59e0b", "#dc2626"],
        )
        fig.update_layout(
            coloraxis_showscale=False,
            yaxis_title="Kalan borç (TL)",
            margin=dict(l=10, r=10, t=50, b=10),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig, width="stretch")
    st.dataframe(
        cards.drop(columns=["id"]),
        width="stretch",
        hide_index=True,
        column_config={
            "Kalan_Borç": st.column_config.NumberColumn("Kalan Borç", format="%.2f TL"),
            "Asgari_Ödeme": st.column_config.NumberColumn("Asgari Ödeme", format="%.2f TL"),
            "Son_Ödeme": "Son Ödeme",
        },
    )


def render_decision_engine() -> None:
    page_header("Aylık Karar Motoru", "Ayın parasına otomatik bir görev dağılımı ver.")
    selected_date = st.date_input("Karar ayı", value=date.today())
    income, expenses = db.get_month_totals(selected_date.year, selected_date.month)
    debt = db.get_total_debt()
    emergency = emergency_fund_value()
    net_worth = calculate_net_worth(db.get_cash(), db.get_investment_value(), debt)
    decision = monthly_decision(
        income=income,
        expenses=expenses,
        total_debt=debt,
        current_emergency_fund=emergency,
        net_worth=net_worth,
    )

    cols = st.columns(3)
    with cols[0]:
        metric_card("Aylık Gelir", format_try(income), selected_date.strftime("%m/%Y"), "good")
    with cols[1]:
        metric_card("Aylık Gider", format_try(expenses), selected_date.strftime("%m/%Y"), "warning")
    with cols[2]:
        metric_card(
            "Kalan Para",
            format_try(decision.remaining_money),
            "Gelir - gider",
            "good" if decision.remaining_money > 0 else "risk",
        )
    alert(decision.warning, decision.risk_level)

    st.subheader("Önerilen dağılım")
    allocation_cols = st.columns(3)
    with allocation_cols[0]:
        metric_card("Karta Ödeme", format_try(decision.debt_payment), "Birinci öncelik", "risk" if debt else "good")
    with allocation_cols[1]:
        metric_card("Acil Durum Fonu", format_try(decision.emergency_fund), "Hedef: 100.000 TL", "warning")
    with allocation_cols[2]:
        metric_card("Yatırım Önerisi", format_try(decision.investment), "Borç durumuna bağlı", "good" if decision.investment else "warning")

    etfs = etf_allocation(decision.investment)
    st.write(
        f"**VOO:** {format_try(etfs['VOO']['tl'])} · "
        f"**QQQM:** {format_try(etfs['QQQM']['tl'])} · "
        f"**SCHD:** {format_try(etfs['SCHD']['tl'])}"
    )
    st.caption("Bu ekran finansal tavsiye değil, girilen verilere dayalı bütçe desteğidir.")


def render_etf_plan() -> None:
    page_header("Midas ETF Planı", "Borç sonrası yatırımını 60/20/20 kuralıyla dağıt.")
    current_portfolio = db.get_investment_value()
    c1, c2 = st.columns(2)
    with c1:
        amount = st.number_input("Yatırım tutarı (TL)", min_value=0.0, step=500.0)
    with c2:
        usd_rate = st.number_input(
            "Dolar kuru (isteğe bağlı)",
            min_value=0.0,
            value=0.0,
            step=0.10,
            help="0 bırakırsanız yalnızca TL dağılımı gösterilir.",
        )
    allocation = etf_allocation(amount, usd_rate or None)
    cols = st.columns(3)
    for column, symbol, status in zip(cols, ["VOO", "QQQM", "SCHD"], ["good", "warning", "warning"]):
        with column:
            usd_note = (
                format_usd(allocation[symbol]["usd"]) if usd_rate > 0 else f"%{allocation[symbol]['weight'] * 100:.0f}"
            )
            metric_card(symbol, format_try(allocation[symbol]["tl"]), usd_note, status)

    if amount > 0:
        chart_frame = pd.DataFrame(
            {
                "ETF": list(allocation.keys()),
                "Tutar": [item["tl"] for item in allocation.values()],
            }
        )
        fig = px.pie(
            chart_frame,
            names="ETF",
            values="Tutar",
            hole=0.58,
            color="ETF",
            color_discrete_map={"VOO": "#2563eb", "QQQM": "#7c3aed", "SCHD": "#16a34a"},
        )
        fig.update_layout(margin=dict(l=10, r=10, t=20, b=10))
        st.plotly_chart(fig, width="stretch")

    st.subheader("Yatırım / portföy kaydı")
    with st.form("investment_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            investment_date = st.date_input("İşlem tarihi", value=date.today())
            portfolio_value = st.number_input(
                "Güncel toplam portföy değeri (TL)",
                min_value=0.0,
                value=float(current_portfolio + amount),
                step=500.0,
            )
        with c2:
            deduct_cash = st.checkbox("Yatırım tutarını nakitten düş", value=True)
            notes = st.text_input("Açıklama")
        submitted = st.form_submit_button("Yatırım Kaydını Kaydet", width="stretch")
        if submitted:
            if amount <= 0 and portfolio_value <= 0:
                st.error("Yatırım tutarı veya portföy değeri girin.")
            elif amount > db.get_cash() and deduct_cash:
                st.error("Yatırım tutarı güncel nakitten büyük olamaz.")
            else:
                db.add_investment(
                    investment_date,
                    amount,
                    usd_rate or None,
                    portfolio_value,
                    notes,
                    deduct_cash,
                )
                st.success("Yatırım kaydı oluşturuldu.")


def render_goals() -> None:
    page_header("Hedefler", "Büyük hedefleri görünür, küçük adımları ölçülebilir yap.")
    db.sync_goal_progress()
    goals = db.query_df("SELECT * FROM goals ORDER BY id")
    for _, goal in goals.iterrows():
        unit = str(goal["unit"])
        current = float(goal["current_amount"])
        target = float(goal["target_amount"])
        progress = min(current / target, 1) if target > 0 else 0
        label_current = format_try(current) if unit == "TL" else format_usd(current)
        label_target = format_try(target) if unit == "TL" else format_usd(target)
        st.markdown(f"#### {goal['name']}")
        st.progress(progress, text=f"{label_current} / {label_target} — %{progress * 100:.1f}")
        if goal["name"] in {"Acil durum fonu", "Uzun vadeli hedef"}:
            with st.expander(f"{goal['name']} tutarını güncelle"):
                new_value = st.number_input(
                    f"Güncel tutar ({unit})",
                    min_value=0.0,
                    value=current,
                    step=500.0,
                    key=f"goal_{int(goal['id'])}",
                )
                if st.button("Hedefi Güncelle", key=f"goal_button_{int(goal['id'])}"):
                    db.update_goal(int(goal["id"]), new_value)
                    st.success("Hedef ilerlemesi güncellendi.")
                    st.rerun()
        st.divider()


def monthly_series(table: str, date_column: str, amount_column: str = "amount") -> pd.DataFrame:
    return db.query_df(
        f"""
        SELECT substr({date_column}, 1, 7) AS Ay, SUM({amount_column}) AS Tutar
        FROM {table}
        GROUP BY substr({date_column}, 1, 7)
        ORDER BY Ay
        """
    )


def debt_reduction_series() -> pd.DataFrame:
    payments = db.query_df(
        """
        SELECT payment_date AS Tarih, SUM(amount) AS Ödeme
        FROM card_payments GROUP BY payment_date ORDER BY payment_date
        """
    )
    current_debt = db.get_total_debt()
    if payments.empty:
        return pd.DataFrame({"Tarih": [date.today().isoformat()], "Kalan_Borç": [current_debt]})
    starting_debt = current_debt + float(payments["Ödeme"].sum())
    values = [starting_debt]
    dates = ["Başlangıç"]
    running = starting_debt
    for _, row in payments.iterrows():
        running -= float(row["Ödeme"])
        dates.append(str(row["Tarih"]))
        values.append(max(running, 0))
    return pd.DataFrame({"Tarih": dates, "Kalan_Borç": values})


def net_worth_series() -> pd.DataFrame:
    income = monthly_series("incomes", "income_date")
    expense = monthly_series("expenses", "expense_date")
    payments = monthly_series("card_payments", "payment_date")
    investments = monthly_series("investments", "investment_date", "total_amount")
    months = sorted(
        set(income.get("Ay", []))
        | set(expense.get("Ay", []))
        | set(payments.get("Ay", []))
        | set(investments.get("Ay", []))
    )
    if not months:
        return pd.DataFrame()

    def to_map(frame: pd.DataFrame) -> dict[str, float]:
        return dict(zip(frame["Ay"], frame["Tutar"])) if not frame.empty else {}

    income_map, expense_map = to_map(income), to_map(expense)
    payment_map, investment_map = to_map(payments), to_map(investments)
    total_flow = sum(income_map.values()) - sum(expense_map.values()) - sum(payment_map.values()) - sum(investment_map.values())
    opening_cash = db.get_cash() - total_flow
    opening_debt = db.get_total_debt() + sum(payment_map.values())
    cash, debt, invested = opening_cash, opening_debt, 0.0
    rows = []
    for month in months:
        cash += income_map.get(month, 0) - expense_map.get(month, 0) - payment_map.get(month, 0) - investment_map.get(month, 0)
        debt = max(debt - payment_map.get(month, 0), 0)
        invested += investment_map.get(month, 0)
        rows.append({"Ay": month, "Net_Servet": cash + invested - debt})
    return pd.DataFrame(rows)


def render_reports() -> None:
    page_header("Raporlar", "Gelir, gider, borç ve servet hareketlerini birlikte oku.")
    income = monthly_series("incomes", "income_date")
    expense = monthly_series("expenses", "expense_date")
    investments = monthly_series("investments", "investment_date", "total_amount")
    debt = debt_reduction_series()
    net_worth = net_worth_series()

    tabs = st.tabs(["Gelir & Gider", "Borç", "Net Servet", "Yatırım"])
    with tabs[0]:
        c1, c2 = st.columns(2)
        with c1:
            fig = monthly_bar_chart(income, "Ay", "Tutar", "Aylık Gelir", "#16a34a")
            st.plotly_chart(fig, width="stretch") if fig else empty_state("Gelir verisi yok.")
        with c2:
            fig = monthly_bar_chart(expense, "Ay", "Tutar", "Aylık Gider", "#dc2626")
            st.plotly_chart(fig, width="stretch") if fig else empty_state("Gider verisi yok.")
    with tabs[1]:
        fig = line_chart(debt, "Tarih", "Kalan_Borç", "Borç Azalımı", "#dc2626")
        st.plotly_chart(fig, width="stretch")
    with tabs[2]:
        fig = line_chart(net_worth, "Ay", "Net_Servet", "Net Servet Gelişimi", "#2563eb")
        st.plotly_chart(fig, width="stretch") if fig else empty_state("Net servet serisi için veri yok.")
    with tabs[3]:
        fig = monthly_bar_chart(investments, "Ay", "Tutar", "Aylık Yatırım", "#7c3aed")
        st.plotly_chart(fig, width="stretch") if fig else empty_state("Henüz yatırım kaydı yok.")


page = render_sidebar()
if page == "Ana Sayfa":
    render_home()
elif page == "Gelir Girişi":
    render_income()
elif page == "Gider Girişi":
    render_expense()
elif page == "Kredi Kartı Borç Merkezi":
    render_debt_center()
elif page == "Aylık Karar Motoru":
    render_decision_engine()
elif page == "Midas ETF Planı":
    render_etf_plan()
elif page == "Hedefler":
    render_goals()
elif page == "Raporlar":
    render_reports()

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterator

import pandas as pd


DB_PATH = Path(os.getenv("ATLAS_DB_PATH", Path(__file__).with_name("atlas.db")))


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS incomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                amount REAL NOT NULL,
                income_date TEXT NOT NULL,
                income_type TEXT NOT NULL DEFAULT 'Maaş',
                description TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                amount REAL NOT NULL,
                expense_date TEXT NOT NULL,
                description TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS credit_cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                total_debt REAL NOT NULL DEFAULT 0,
                minimum_payment REAL NOT NULL DEFAULT 0,
                due_date TEXT,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS card_payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                payment_date TEXT NOT NULL,
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (card_id) REFERENCES credit_cards(id)
            );

            CREATE TABLE IF NOT EXISTS investments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                investment_date TEXT NOT NULL,
                total_amount REAL NOT NULL,
                voo_amount REAL NOT NULL DEFAULT 0,
                qqqm_amount REAL NOT NULL DEFAULT 0,
                schd_amount REAL NOT NULL DEFAULT 0,
                usd_rate REAL,
                portfolio_value REAL,
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS goals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                target_amount REAL NOT NULL,
                current_amount REAL NOT NULL DEFAULT 0,
                unit TEXT NOT NULL DEFAULT 'TL'
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )
        _seed_data(conn)


def _seed_data(conn: sqlite3.Connection) -> None:
    seeded = conn.execute(
        "SELECT value FROM settings WHERE key = 'seeded'"
    ).fetchone()
    if seeded:
        return

    current_year = date.today().year
    conn.executemany(
        """
        INSERT INTO credit_cards (name, total_debt, minimum_payment, due_date)
        VALUES (?, ?, ?, ?)
        """,
        [
            ("Ziraat", 44077.23, 0, f"{current_year}-07-22"),
            ("Akbank", 2000.00, 0, f"{current_year}-07-22"),
            ("İş Bankası", 2000.00, 0, f"{current_year}-07-22"),
        ],
    )
    conn.execute(
        """
        INSERT INTO incomes (amount, income_date, income_type, description)
        VALUES (?, ?, ?, ?)
        """,
        (32500.00, f"{current_year}-07-16", "Maaş", "Temmuz maaşı (örnek veri)"),
    )
    conn.execute(
        """
        INSERT INTO expenses (category, amount, expense_date, description)
        VALUES (?, ?, ?, ?)
        """,
        ("Kira", 22500.00, f"{current_year}-07-13", "Aylık kira (örnek veri)"),
    )
    conn.executemany(
        """
        INSERT INTO goals (name, target_amount, current_amount, unit)
        VALUES (?, ?, ?, ?)
        """,
        [
            ("Kredi kartı borcu 0 TL", 48077.23, 0, "TL"),
            ("Acil durum fonu", 100000.00, 35000.00, "TL"),
            ("İlk yatırım portföyü", 100000.00, 0, "TL"),
            ("Uzun vadeli hedef", 100000.00, 0, "USD"),
        ],
    )
    conn.executemany(
        "INSERT INTO settings (key, value) VALUES (?, ?)",
        [("current_cash", "35000"), ("seeded", datetime.now().isoformat())],
    )


def execute(query: str, params: tuple[Any, ...] = ()) -> int:
    with get_connection() as conn:
        cursor = conn.execute(query, params)
        return int(cursor.lastrowid)


def query_df(query: str, params: tuple[Any, ...] = ()) -> pd.DataFrame:
    with get_connection() as conn:
        return pd.read_sql_query(query, conn, params=params)


def get_setting(key: str, default: float | str = 0) -> str:
    with get_connection() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return str(row["value"]) if row else str(default)


def set_setting(key: str, value: float | str) -> None:
    execute(
        """
        INSERT INTO settings (key, value) VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (key, str(value)),
    )


def get_cash() -> float:
    return float(get_setting("current_cash", 0))


def set_cash(amount: float) -> None:
    set_setting("current_cash", max(float(amount), 0))
    sync_goal_progress()


def adjust_cash(delta: float) -> None:
    set_cash(get_cash() + float(delta))


def add_income(
    amount: float,
    income_date: date,
    income_type: str,
    description: str,
    update_cash: bool = True,
) -> int:
    row_id = execute(
        """
        INSERT INTO incomes (amount, income_date, income_type, description)
        VALUES (?, ?, ?, ?)
        """,
        (amount, income_date.isoformat(), income_type, description),
    )
    if update_cash:
        adjust_cash(amount)
    return row_id


def add_expense(
    category: str,
    amount: float,
    expense_date: date,
    description: str,
    update_cash: bool = True,
) -> int:
    row_id = execute(
        """
        INSERT INTO expenses (category, amount, expense_date, description)
        VALUES (?, ?, ?, ?)
        """,
        (category, amount, expense_date.isoformat(), description),
    )
    if update_cash:
        adjust_cash(-amount)
    return row_id


def upsert_credit_card(
    name: str, total_debt: float, minimum_payment: float, due_date: date
) -> int:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO credit_cards (name, total_debt, minimum_payment, due_date)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                total_debt = excluded.total_debt,
                minimum_payment = excluded.minimum_payment,
                due_date = excluded.due_date,
                updated_at = CURRENT_TIMESTAMP
            """,
            (name, total_debt, minimum_payment, due_date.isoformat()),
        )
        row = conn.execute(
            "SELECT id FROM credit_cards WHERE name = ?", (name,)
        ).fetchone()
    sync_goal_progress()
    return int(row["id"])


def add_card_payment(
    card_id: int,
    amount: float,
    payment_date: date,
    notes: str,
    update_cash: bool = True,
) -> None:
    if amount <= 0:
        return
    with get_connection() as conn:
        debt_row = conn.execute(
            "SELECT total_debt FROM credit_cards WHERE id = ?", (card_id,)
        ).fetchone()
        if not debt_row:
            raise ValueError("Kredi kartı bulunamadı.")
        paid = min(float(amount), float(debt_row["total_debt"]))
        conn.execute(
            """
            INSERT INTO card_payments (card_id, amount, payment_date, notes)
            VALUES (?, ?, ?, ?)
            """,
            (card_id, paid, payment_date.isoformat(), notes),
        )
        conn.execute(
            """
            UPDATE credit_cards
            SET total_debt = MAX(total_debt - ?, 0), updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (paid, card_id),
        )
    if update_cash:
        adjust_cash(-paid)
    sync_goal_progress()


def add_investment(
    investment_date: date,
    total_amount: float,
    usd_rate: float | None,
    portfolio_value: float,
    notes: str,
    update_cash: bool = True,
) -> None:
    execute(
        """
        INSERT INTO investments (
            investment_date, total_amount, voo_amount, qqqm_amount, schd_amount,
            usd_rate, portfolio_value, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            investment_date.isoformat(),
            total_amount,
            total_amount * 0.60,
            total_amount * 0.20,
            total_amount * 0.20,
            usd_rate,
            portfolio_value,
            notes,
        ),
    )
    if update_cash:
        adjust_cash(-total_amount)
    sync_goal_progress()


def update_goal(goal_id: int, current_amount: float) -> None:
    execute(
        "UPDATE goals SET current_amount = MAX(?, 0) WHERE id = ?",
        (current_amount, goal_id),
    )


def sync_goal_progress() -> None:
    total_debt = float(
        query_df("SELECT COALESCE(SUM(total_debt), 0) AS value FROM credit_cards").iloc[
            0
        ]["value"]
    )
    investment_value = get_investment_value()
    execute(
        """
        UPDATE goals
        SET current_amount = MAX(target_amount - ?, 0)
        WHERE name = 'Kredi kartı borcu 0 TL'
        """,
        (total_debt,),
    )
    execute(
        """
        UPDATE goals SET current_amount = ?
        WHERE name = 'İlk yatırım portföyü'
        """,
        (investment_value,),
    )


def get_investment_value() -> float:
    frame = query_df(
        """
        SELECT COALESCE(
            (SELECT portfolio_value FROM investments ORDER BY investment_date DESC, id DESC LIMIT 1),
            (SELECT SUM(total_amount) FROM investments),
            0
        ) AS value
        """
    )
    return float(frame.iloc[0]["value"] or 0)


def get_total_debt() -> float:
    frame = query_df("SELECT COALESCE(SUM(total_debt), 0) AS value FROM credit_cards")
    return float(frame.iloc[0]["value"])


def get_month_totals(year: int, month: int) -> tuple[float, float]:
    month_key = f"{year:04d}-{month:02d}"
    income = query_df(
        """
        SELECT COALESCE(SUM(amount), 0) AS value
        FROM incomes WHERE substr(income_date, 1, 7) = ?
        """,
        (month_key,),
    )
    expense = query_df(
        """
        SELECT COALESCE(SUM(amount), 0) AS value
        FROM expenses WHERE substr(expense_date, 1, 7) = ?
        """,
        (month_key,),
    )
    return float(income.iloc[0]["value"]), float(expense.iloc[0]["value"])


def has_minimum_payment_habit() -> bool:
    frame = query_df(
        """
        SELECT p.amount, c.minimum_payment
        FROM card_payments p
        JOIN credit_cards c ON c.id = p.card_id
        WHERE c.minimum_payment > 0
        ORDER BY p.payment_date DESC, p.id DESC
        LIMIT 3
        """
    )
    return bool(len(frame) >= 2 and (frame["amount"] <= frame["minimum_payment"] * 1.05).all())


def has_regular_investment() -> bool:
    frame = query_df(
        """
        SELECT COUNT(DISTINCT substr(investment_date, 1, 7)) AS month_count
        FROM investments
        WHERE investment_date >= date('now', '-4 months')
        """
    )
    return int(frame.iloc[0]["month_count"]) >= 2


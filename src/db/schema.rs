use anyhow::Result;
use rusqlite::Connection;

/// Creates the database tables for the share tracking system
pub fn create_tables(conn: &Connection) -> Result<()> {
    // Create stocks table
    conn.execute(
        "CREATE TABLE IF NOT EXISTS stocks (
            id INTEGER PRIMARY KEY,
            symbol TEXT NOT NULL UNIQUE
        )",
        [],
    )?;

    // Create buy transactions table
    conn.execute(
        "CREATE TABLE IF NOT EXISTS buy_transactions (
            id INTEGER PRIMARY KEY,
            stock_id TEXT NOT NULL,
            date TEXT NOT NULL, -- ISO-8601 format: YYYY-MM-DD
            quantity INTEGER NOT NULL,
            price_per_share REAL NOT NULL,
            fees REAL NOT NULL,
            notes TEXT,
            FOREIGN KEY (stock_id) REFERENCES stocks(symbol)
        )",
        [],
    )?;

    // Create sell transactions table
    conn.execute(
        "CREATE TABLE IF NOT EXISTS sell_transactions (
            id INTEGER PRIMARY KEY,
            stock_id TEXT NOT NULL,
            date TEXT NOT NULL, -- ISO-8601 format: YYYY-MM-DD
            quantity INTEGER NOT NULL,
            price_per_share REAL NOT NULL,
            fees REAL NOT NULL,
            notes TEXT,
            FOREIGN KEY (stock_id) REFERENCES stocks(symbol)
        )",
        [],
    )?;

    // Create sell allocations table to link sell transactions to buy transactions
    conn.execute(
        "CREATE TABLE IF NOT EXISTS sell_allocations (
            id INTEGER PRIMARY KEY,
            sell_transaction_id INTEGER NOT NULL,
            buy_transaction_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            allocated_buy_price REAL NOT NULL,
            allocated_buy_fees REAL NOT NULL,
            capital_gain REAL NOT NULL,
            cgt_discount_applied INTEGER NOT NULL,
            FOREIGN KEY (sell_transaction_id) REFERENCES sell_transactions(id),
            FOREIGN KEY (buy_transaction_id) REFERENCES buy_transactions(id)
        )",
        [],
    )?;

    Ok(())
}

/// Drops all database tables in the correct order
pub fn drop_tables(conn: &Connection) -> Result<()> {
    conn.execute("PRAGMA foreign_keys = OFF", [])?;
    conn.execute("DROP TABLE IF EXISTS sell_allocations", [])?;
    conn.execute("DROP TABLE IF EXISTS sell_transactions", [])?;
    conn.execute("DROP TABLE IF EXISTS buy_transactions", [])?;
    conn.execute("DROP TABLE IF EXISTS stocks", [])?;
    conn.execute("PRAGMA foreign_keys = ON", [])?;
    Ok(())
}

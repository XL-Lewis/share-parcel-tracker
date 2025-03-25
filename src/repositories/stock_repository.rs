use anyhow::Result;
use rusqlite::{params, Connection};

use crate::models::Stock;

/// Repository for stock operations in the database
pub struct StockRepository<'a> {
    conn: &'a Connection,
}

impl<'a> StockRepository<'a> {
    /// Create a new StockRepository with a connection
    pub fn new(conn: &'a Connection) -> Self {
        Self { conn }
    }

    /// Find a stock by its symbol, returns None if not found
    pub fn find_by_symbol(&self, symbol: &str) -> Result<Option<Stock>> {
        let mut stmt = self
            .conn
            .prepare("SELECT id, symbol FROM stocks WHERE symbol = ?1")?;
        let mut rows = stmt.query(params![symbol])?;

        if let Some(row) = rows.next()? {
            let id = row.get(0)?;
            let symbol = row.get(1)?;
            Ok(Some(Stock {
                id: Some(id),
                symbol,
            }))
        } else {
            Ok(None)
        }
    }

    /// Insert a new stock, or ignore if already exists
    pub fn insert_if_not_exists(&self, stock: &Stock) -> Result<()> {
        self.conn.execute(
            "INSERT OR IGNORE INTO stocks (symbol) VALUES (?1)",
            params![stock.symbol],
        )?;
        Ok(())
    }

    /// Get all stocks in the database
    pub fn get_all(&self) -> Result<Vec<Stock>> {
        let mut stmt = self
            .conn
            .prepare("SELECT id, symbol FROM stocks ORDER BY symbol")?;

        let stock_iter = stmt.query_map([], |row| {
            Ok(Stock {
                id: Some(row.get(0)?),
                symbol: row.get(1)?,
            })
        })?;

        let mut stocks = Vec::new();
        for stock in stock_iter {
            stocks.push(stock?);
        }

        Ok(stocks)
    }

    /// Delete a stock by its symbol
    pub fn delete_by_symbol(&self, symbol: &str) -> Result<bool> {
        let deleted = self
            .conn
            .execute("DELETE FROM stocks WHERE symbol = ?1", params![symbol])?;

        Ok(deleted > 0)
    }
}

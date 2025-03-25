use anyhow::Result;
use rusqlite::Connection;

use crate::models::Stock;
use crate::repositories::StockRepository;

/// Service for stock-related operations
pub struct StockService<'a> {
    conn: &'a Connection,
}

impl<'a> StockService<'a> {
    /// Create a new StockService with a database connection
    pub fn new(conn: &'a Connection) -> Self {
        Self { conn }
    }

    /// Ensure a stock exists in the database, creating it if needed
    pub fn ensure_stock_exists(&self, symbol: &str) -> Result<()> {
        let repo = StockRepository::new(self.conn);
        let stock = Stock::new(symbol.to_string());
        repo.insert_if_not_exists(&stock)
    }

    /// Get all stocks in the database
    pub fn get_all_stocks(&self) -> Result<Vec<Stock>> {
        let repo = StockRepository::new(self.conn);
        repo.get_all()
    }

    /// Find a stock by its symbol
    pub fn find_stock_by_symbol(&self, symbol: &str) -> Result<Option<Stock>> {
        let repo = StockRepository::new(self.conn);
        repo.find_by_symbol(symbol)
    }
}

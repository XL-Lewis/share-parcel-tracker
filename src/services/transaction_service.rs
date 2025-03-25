use anyhow::Result;
use rusqlite::Connection;

use crate::date::Date;
use crate::models::{BuyTransaction, SellTransaction};
use crate::repositories::{BuyTransactionRepository, SellTransactionRepository};
use crate::services::StockService;

/// Service for transaction-related operations
pub struct TransactionService<'a> {
    conn: &'a Connection,
}

impl<'a> TransactionService<'a> {
    /// Create a new TransactionService with a database connection
    pub fn new(conn: &'a Connection) -> Self {
        Self { conn }
    }

    /// Add a new buy transaction
    pub fn add_buy_transaction(
        &self,
        stock_id: &str,
        date: Date,
        quantity: u32,
        price_per_share: f64,
        fees: f64,
        notes: Option<String>,
    ) -> Result<i64> {
        // Ensure stock exists
        let stock_service = StockService::new(self.conn);
        stock_service.ensure_stock_exists(stock_id)?;

        // Create and insert transaction
        let transaction = BuyTransaction::new(
            stock_id.to_string(),
            date,
            quantity,
            price_per_share,
            fees,
            notes,
        );

        let repo = BuyTransactionRepository::new(self.conn);
        repo.insert(&transaction)
    }

    /// Add a new sell transaction
    pub fn add_sell_transaction(
        &self,
        stock_id: &str,
        date: Date,
        quantity: u32,
        price_per_share: f64,
        fees: f64,
        notes: Option<String>,
    ) -> Result<i64> {
        // Ensure stock exists
        let stock_service = StockService::new(self.conn);
        stock_service.ensure_stock_exists(stock_id)?;

        // Create and insert transaction
        let transaction = SellTransaction::new(
            stock_id.to_string(),
            date,
            quantity,
            price_per_share,
            fees,
            notes,
        );

        let repo = SellTransactionRepository::new(self.conn);
        let sell_id = repo.insert(&transaction)?;

        Ok(sell_id)
    }

    /// Get all buy transactions
    pub fn get_all_buy_transactions(&self) -> Result<Vec<BuyTransaction>> {
        let repo = BuyTransactionRepository::new(self.conn);
        repo.get_all()
    }

    /// Get all sell transactions
    pub fn get_all_sell_transactions(&self) -> Result<Vec<SellTransaction>> {
        let repo = SellTransactionRepository::new(self.conn);
        repo.get_all()
    }

    /// Get a buy transaction by ID
    pub fn get_buy_transaction(&self, id: i32) -> Result<Option<BuyTransaction>> {
        let repo = BuyTransactionRepository::new(self.conn);
        repo.find_by_id(id)
    }

    /// Get a sell transaction by ID
    pub fn get_sell_transaction(&self, id: i32) -> Result<Option<SellTransaction>> {
        let repo = SellTransactionRepository::new(self.conn);
        repo.find_by_id(id)
    }

    /// Get available buy transactions for a stock that can be allocated to a sell
    pub fn get_available_buys_for_stock(
        &self,
        stock_id: &str,
    ) -> Result<Vec<(BuyTransaction, u32)>> {
        let repo = BuyTransactionRepository::new(self.conn);
        repo.find_available_buys_for_stock(stock_id)
    }
}

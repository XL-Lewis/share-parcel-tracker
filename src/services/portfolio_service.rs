use anyhow::Result;
use rusqlite::Connection;
use std::collections::HashMap;

use crate::models::Stock;
use crate::repositories::{BuyTransactionRepository, SellTransactionRepository};

/// Service for portfolio-related operations
pub struct PortfolioService<'a> {
    conn: &'a Connection,
}

impl<'a> PortfolioService<'a> {
    /// Create a new PortfolioService with a database connection
    pub fn new(conn: &'a Connection) -> Self {
        Self { conn }
    }

    /// Get the current holdings for all stocks
    pub fn get_current_holdings(&self) -> Result<HashMap<String, u32>> {
        let mut holdings: HashMap<String, u32> = HashMap::new();

        // Get buy transactions
        let buy_repo = BuyTransactionRepository::new(self.conn);
        let buy_transactions = buy_repo.get_all()?;

        // Add all buy transactions to holdings
        for tx in buy_transactions {
            *holdings.entry(tx.stock_id).or_insert(0) += tx.quantity;
        }

        // Get sell transactions
        let sell_repo = SellTransactionRepository::new(self.conn);
        let sell_transactions = sell_repo.get_all()?;

        // Subtract all sell transactions from holdings
        for tx in sell_transactions {
            *holdings.entry(tx.stock_id).or_insert(0) -= tx.quantity;
        }

        Ok(holdings)
    }

    /// Get current holdings for a specific stock
    pub fn get_holdings_for_stock(&self, stock_id: &str) -> Result<u32> {
        let holdings = self.get_current_holdings()?;
        Ok(*holdings.get(stock_id).unwrap_or(&0))
    }

    /// Get only stocks with positive holdings
    pub fn get_active_holdings(&self) -> Result<HashMap<String, u32>> {
        let all_holdings = self.get_current_holdings()?;

        // Filter to only include stocks with positive holdings
        let active_holdings = all_holdings
            .into_iter()
            .filter(|(_, qty)| *qty > 0)
            .collect();

        Ok(active_holdings)
    }
}

use anyhow::{anyhow, Result};
use rusqlite::Connection;

use crate::date::Date;
use crate::models::SellAllocation;
use crate::repositories::{SellAllocationRepository, SellTransactionRepository};
use crate::services::TransactionService;

/// Service for allocation-related operations
pub struct AllocationService<'a> {
    conn: &'a Connection,
}

impl<'a> AllocationService<'a> {
    /// Create a new AllocationService with a database connection
    pub fn new(conn: &'a Connection) -> Self {
        Self { conn }
    }

    /// Check if a sell transaction already has allocations
    pub fn has_allocations(&self, sell_transaction_id: i32) -> Result<bool> {
        let repo = SellAllocationRepository::new(self.conn);
        repo.has_allocations(sell_transaction_id)
    }

    /// Allocate a sell transaction to buy transactions using FIFO method
    pub fn allocate_sell_transaction_fifo(&self, sell_transaction_id: i32) -> Result<()> {
        // Check if this sell transaction already has allocations
        if self.has_allocations(sell_transaction_id)? {
            // Already allocated, skip to avoid duplicates
            return Ok(());
        }

        // Get sell transaction details
        let sell_repo = SellTransactionRepository::new(self.conn);
        let sell_transaction = sell_repo
            .find_by_id(sell_transaction_id)?
            .ok_or_else(|| anyhow!("Sell transaction not found: {}", sell_transaction_id))?;

        // Get all buy transactions for this stock with remaining quantity
        let tx_service = TransactionService::new(self.conn);
        let buy_txs = tx_service.get_available_buys_for_stock(&sell_transaction.stock_id)?;

        let mut remaining_to_allocate = sell_transaction.quantity;
        let alloc_repo = SellAllocationRepository::new(self.conn);

        for (buy_tx, remaining_quantity) in buy_txs {
            if remaining_to_allocate == 0 {
                break;
            }

            if remaining_quantity == 0 {
                continue; // Skip if no remaining quantity
            }

            let buy_id = buy_tx
                .id
                .ok_or_else(|| anyhow!("Buy transaction has no ID"))?;

            // Calculate allocation quantity
            let allocation_quantity = std::cmp::min(remaining_to_allocate, remaining_quantity);

            // Calculate proportions
            let proportion = allocation_quantity as f64 / buy_tx.quantity as f64;

            // Calculate allocated amounts
            let allocated_buy_price = buy_tx.price_per_share * allocation_quantity as f64;
            let allocated_buy_fees = buy_tx.fees * proportion;

            // Calculate proportional sell amount and fees
            let allocated_sell_price =
                sell_transaction.price_per_share * allocation_quantity as f64;
            let allocated_sell_fees = sell_transaction.fees
                * (allocation_quantity as f64 / sell_transaction.quantity as f64);

            // Calculate capital gain/loss
            let cost_basis = allocated_buy_price + allocated_buy_fees;
            let proceeds = allocated_sell_price - allocated_sell_fees;
            let capital_gain = proceeds - cost_basis;

            // Check if CGT discount applies (held for more than 1 year)
            let cgt_discount_applied =
                Date::is_eligible_for_cgt_discount(&buy_tx.date, &sell_transaction.date);

            // Create allocation record
            let allocation = SellAllocation::new(
                sell_transaction_id,
                buy_id,
                allocation_quantity,
                allocated_buy_price,
                allocated_buy_fees,
                capital_gain,
                cgt_discount_applied,
            );

            alloc_repo.insert(&allocation)?;

            // Update remaining to allocate
            remaining_to_allocate -= allocation_quantity;
        }

        // Check if we've allocated all shares
        if remaining_to_allocate > 0 {
            return Err(anyhow!(
                "Could not allocate all shares for sell transaction {}: {} remaining",
                sell_transaction_id,
                remaining_to_allocate
            ));
        }

        Ok(())
    }

    /// Get all allocations
    pub fn get_all_allocations(&self) -> Result<Vec<SellAllocation>> {
        let repo = SellAllocationRepository::new(self.conn);
        repo.get_all()
    }

    /// Get allocations for a specific sell transaction
    pub fn get_allocations_for_sell(
        &self,
        sell_transaction_id: i32,
    ) -> Result<Vec<SellAllocation>> {
        let repo = SellAllocationRepository::new(self.conn);
        repo.find_by_sell_transaction_id(sell_transaction_id)
    }

    /// Get capital gains by stock for a specific financial year
    pub fn get_capital_gains_by_stock(&self, fy: &str) -> Result<Vec<(String, f64, f64, f64)>> {
        // Financial years in Australia are formatted as "2023-2024" for FY starting July 1, 2023
        let parts: Vec<&str> = fy.split('-').collect();
        let start_year: u32 = parts[0].parse()?;
        let end_year: u32 = parts[1].parse()?;

        let repo = SellAllocationRepository::new(self.conn);
        repo.get_capital_gains_by_stock(start_year, end_year)
    }
}

use anyhow::Result;
use rusqlite::{params, Connection};

use crate::date::Date;
use crate::models::SellAllocation;

/// Repository for sell allocation operations in the database
pub struct SellAllocationRepository<'a> {
    conn: &'a Connection,
}

impl<'a> SellAllocationRepository<'a> {
    /// Create a new SellAllocationRepository with a connection
    pub fn new(conn: &'a Connection) -> Self {
        Self { conn }
    }

    /// Insert a new sell allocation
    pub fn insert(&self, allocation: &SellAllocation) -> Result<i64> {
        self.conn.execute(
            "INSERT INTO sell_allocations (
                sell_transaction_id, buy_transaction_id, quantity,
                allocated_buy_price, allocated_buy_fees,
                capital_gain, cgt_discount_applied
            ) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)",
            params![
                allocation.sell_transaction_id,
                allocation.buy_transaction_id,
                allocation.quantity,
                allocation.allocated_buy_price,
                allocation.allocated_buy_fees,
                allocation.capital_gain,
                if allocation.cgt_discount_applied {
                    1
                } else {
                    0
                }
            ],
        )?;

        Ok(self.conn.last_insert_rowid())
    }

    /// Check if a sell transaction already has allocations
    pub fn has_allocations(&self, sell_transaction_id: i32) -> Result<bool> {
        let count: i64 = self.conn.query_row(
            "SELECT COUNT(*) FROM sell_allocations WHERE sell_transaction_id = ?1",
            params![sell_transaction_id],
            |row| row.get(0),
        )?;

        Ok(count > 0)
    }

    /// Find allocations by sell transaction ID
    pub fn find_by_sell_transaction_id(
        &self,
        sell_transaction_id: i32,
    ) -> Result<Vec<SellAllocation>> {
        let mut stmt = self.conn.prepare(
            "SELECT id, sell_transaction_id, buy_transaction_id, quantity, 
                    allocated_buy_price, allocated_buy_fees, capital_gain, cgt_discount_applied
             FROM sell_allocations
             WHERE sell_transaction_id = ?1
             ORDER BY buy_transaction_id",
        )?;

        let alloc_iter = stmt.query_map(params![sell_transaction_id], |row| {
            Ok(SellAllocation {
                id: Some(row.get(0)?),
                sell_transaction_id: row.get(1)?,
                buy_transaction_id: row.get(2)?,
                quantity: row.get(3)?,
                allocated_buy_price: row.get(4)?,
                allocated_buy_fees: row.get(5)?,
                capital_gain: row.get(6)?,
                cgt_discount_applied: row.get::<_, i32>(7)? != 0,
            })
        })?;

        let mut allocations = Vec::new();
        for alloc in alloc_iter {
            allocations.push(alloc?);
        }

        Ok(allocations)
    }

    /// Find allocations in a specific financial year
    pub fn find_by_financial_year(
        &self,
        start_year: u32,
        end_year: u32,
    ) -> Result<Vec<SellAllocation>> {
        let mut stmt = self.conn.prepare(
            "SELECT sa.id, sa.sell_transaction_id, sa.buy_transaction_id, sa.quantity, 
                    sa.allocated_buy_price, sa.allocated_buy_fees, sa.capital_gain, sa.cgt_discount_applied
             FROM sell_allocations sa
             JOIN sell_transactions st ON sa.sell_transaction_id = st.id
             WHERE
                (strftime('%Y', st.date) = ?1 AND strftime('%m', st.date) >= '07') OR
                (strftime('%Y', st.date) = ?2 AND strftime('%m', st.date) <= '06')
             ORDER BY st.stock_id, st.date",
        )?;

        let alloc_iter = stmt.query_map(
            params![start_year.to_string(), end_year.to_string()],
            |row| {
                Ok(SellAllocation {
                    id: Some(row.get(0)?),
                    sell_transaction_id: row.get(1)?,
                    buy_transaction_id: row.get(2)?,
                    quantity: row.get(3)?,
                    allocated_buy_price: row.get(4)?,
                    allocated_buy_fees: row.get(5)?,
                    capital_gain: row.get(6)?,
                    cgt_discount_applied: row.get::<_, i32>(7)? != 0,
                })
            },
        )?;

        let mut allocations = Vec::new();
        for alloc in alloc_iter {
            allocations.push(alloc?);
        }

        Ok(allocations)
    }

    /// Get capital gains by stock for a specific financial year
    pub fn get_capital_gains_by_stock(
        &self,
        start_year: u32,
        end_year: u32,
    ) -> Result<Vec<(String, f64, f64, f64)>> {
        let mut stmt = self.conn.prepare(
            "SELECT
                bt.stock_id,
                SUM(CASE WHEN sa.capital_gain > 0 AND sa.cgt_discount_applied = 0 THEN sa.capital_gain ELSE 0 END) as short_term,
                SUM(CASE WHEN sa.capital_gain > 0 AND sa.cgt_discount_applied = 1 THEN sa.capital_gain ELSE 0 END) as long_term,
                SUM(CASE WHEN sa.capital_gain < 0 THEN -sa.capital_gain ELSE 0 END) as losses
             FROM sell_allocations sa
             JOIN buy_transactions bt ON sa.buy_transaction_id = bt.id
             JOIN sell_transactions st ON sa.sell_transaction_id = st.id
             WHERE
                (strftime('%Y', st.date) = ?1 AND strftime('%m', st.date) >= '07') OR
                (strftime('%Y', st.date) = ?2 AND strftime('%m', st.date) <= '06')
             GROUP BY bt.stock_id
             ORDER BY bt.stock_id"
        )?;

        let rows = stmt.query_map(
            params![start_year.to_string(), end_year.to_string()],
            |row| {
                let stock_id: String = row.get(0)?;
                let short_term: f64 = row.get(1)?;
                let long_term: f64 = row.get(2)?;
                let losses: f64 = row.get(3)?;

                Ok((stock_id, short_term, long_term, losses))
            },
        )?;

        let mut results = Vec::new();
        for row_result in rows {
            results.push(row_result?);
        }

        Ok(results)
    }

    /// Get all sell allocations
    pub fn get_all(&self) -> Result<Vec<SellAllocation>> {
        let mut stmt = self.conn.prepare(
            "SELECT id, sell_transaction_id, buy_transaction_id, quantity, 
                    allocated_buy_price, allocated_buy_fees, capital_gain, cgt_discount_applied
             FROM sell_allocations
             ORDER BY sell_transaction_id, buy_transaction_id",
        )?;

        let alloc_iter = stmt.query_map([], |row| {
            Ok(SellAllocation {
                id: Some(row.get(0)?),
                sell_transaction_id: row.get(1)?,
                buy_transaction_id: row.get(2)?,
                quantity: row.get(3)?,
                allocated_buy_price: row.get(4)?,
                allocated_buy_fees: row.get(5)?,
                capital_gain: row.get(6)?,
                cgt_discount_applied: row.get::<_, i32>(7)? != 0,
            })
        })?;

        let mut allocations = Vec::new();
        for alloc in alloc_iter {
            allocations.push(alloc?);
        }

        Ok(allocations)
    }
}

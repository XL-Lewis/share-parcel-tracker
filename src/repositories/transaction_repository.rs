use anyhow::Result;
use rusqlite::{params, Connection};

use crate::date::Date;
use crate::models::{BuyTransaction, SellTransaction};

/// Repository for buy transaction operations in the database
pub struct BuyTransactionRepository<'a> {
    conn: &'a Connection,
}

impl<'a> BuyTransactionRepository<'a> {
    /// Create a new BuyTransactionRepository with a connection
    pub fn new(conn: &'a Connection) -> Self {
        Self { conn }
    }

    /// Insert a new buy transaction
    pub fn insert(&self, transaction: &BuyTransaction) -> Result<i64> {
        self.conn.execute(
            "INSERT INTO buy_transactions (stock_id, date, quantity, price_per_share, fees, notes)
             VALUES (?1, ?2, ?3, ?4, ?5, ?6)",
            params![
                transaction.stock_id,
                transaction.date.to_string(),
                transaction.quantity,
                transaction.price_per_share,
                transaction.fees,
                transaction.notes,
            ],
        )?;

        Ok(self.conn.last_insert_rowid())
    }

    /// Find a buy transaction by ID
    pub fn find_by_id(&self, id: i32) -> Result<Option<BuyTransaction>> {
        let mut stmt = self.conn.prepare(
            "SELECT id, stock_id, date, quantity, price_per_share, fees, notes
             FROM buy_transactions WHERE id = ?1",
        )?;

        let mut rows = stmt.query(params![id])?;

        if let Some(row) = rows.next()? {
            Ok(Some(BuyTransaction {
                id: Some(row.get(0)?),
                stock_id: row.get(1)?,
                date: row.get::<_, String>(2)?.try_into().unwrap(),
                quantity: row.get(3)?,
                price_per_share: row.get(4)?,
                fees: row.get(5)?,
                notes: row.get(6)?,
            }))
        } else {
            Ok(None)
        }
    }

    /// Get all buy transactions for a specific stock
    pub fn find_by_stock_id(&self, stock_id: &str) -> Result<Vec<BuyTransaction>> {
        let mut stmt = self.conn.prepare(
            "SELECT id, stock_id, date, quantity, price_per_share, fees, notes
             FROM buy_transactions
             WHERE stock_id = ?1
             ORDER BY date",
        )?;

        let tx_iter = stmt.query_map(params![stock_id], |row| {
            Ok(BuyTransaction {
                id: Some(row.get(0)?),
                stock_id: row.get(1)?,
                date: row.get::<_, String>(2)?.try_into().unwrap(),
                quantity: row.get(3)?,
                price_per_share: row.get(4)?,
                fees: row.get(5)?,
                notes: row.get(6)?,
            })
        })?;

        let mut transactions = Vec::new();
        for tx in tx_iter {
            transactions.push(tx?);
        }

        Ok(transactions)
    }

    /// Get all buy transactions with their remaining quantities
    pub fn find_available_buys_for_stock(
        &self,
        stock_id: &str,
    ) -> Result<Vec<(BuyTransaction, u32)>> {
        let mut stmt = self.conn.prepare(
            "SELECT bt.id, bt.stock_id, bt.date, bt.quantity, bt.price_per_share, bt.fees, bt.notes,
                   (SELECT COALESCE(SUM(sa.quantity), 0) FROM sell_allocations sa WHERE sa.buy_transaction_id = bt.id) as allocated
             FROM buy_transactions bt
             WHERE bt.stock_id = ?1
             ORDER BY bt.date", // FIFO - oldest first
        )?;

        let tx_iter = stmt.query_map(params![stock_id], |row| {
            let tx = BuyTransaction {
                id: Some(row.get(0)?),
                stock_id: row.get(1)?,
                date: row.get::<_, String>(2)?.try_into().unwrap(),
                quantity: row.get(3)?,
                price_per_share: row.get(4)?,
                fees: row.get(5)?,
                notes: row.get(6)?,
            };
            let allocated: u32 = row.get(7)?;
            let remaining = tx.quantity - allocated;

            Ok((tx, remaining))
        })?;

        let mut results = Vec::new();
        for tx_result in tx_iter {
            results.push(tx_result?);
        }

        Ok(results)
    }

    /// Get all buy transactions
    pub fn get_all(&self) -> Result<Vec<BuyTransaction>> {
        let mut stmt = self.conn.prepare(
            "SELECT id, stock_id, date, quantity, price_per_share, fees, notes
             FROM buy_transactions
             ORDER BY date",
        )?;

        let tx_iter = stmt.query_map([], |row| {
            Ok(BuyTransaction {
                id: Some(row.get(0)?),
                stock_id: row.get(1)?,
                date: row.get::<_, String>(2)?.try_into().unwrap(),
                quantity: row.get(3)?,
                price_per_share: row.get(4)?,
                fees: row.get(5)?,
                notes: row.get(6)?,
            })
        })?;

        let mut transactions = Vec::new();
        for tx in tx_iter {
            transactions.push(tx?);
        }

        Ok(transactions)
    }
}

/// Repository for sell transaction operations in the database
pub struct SellTransactionRepository<'a> {
    conn: &'a Connection,
}

impl<'a> SellTransactionRepository<'a> {
    /// Create a new SellTransactionRepository with a connection
    pub fn new(conn: &'a Connection) -> Self {
        Self { conn }
    }

    /// Insert a new sell transaction
    pub fn insert(&self, transaction: &SellTransaction) -> Result<i64> {
        self.conn.execute(
            "INSERT INTO sell_transactions (stock_id, date, quantity, price_per_share, fees, notes)
             VALUES (?1, ?2, ?3, ?4, ?5, ?6)",
            params![
                transaction.stock_id,
                transaction.date.to_string(),
                transaction.quantity,
                transaction.price_per_share,
                transaction.fees,
                transaction.notes,
            ],
        )?;

        Ok(self.conn.last_insert_rowid())
    }

    /// Find a sell transaction by ID
    pub fn find_by_id(&self, id: i32) -> Result<Option<SellTransaction>> {
        let mut stmt = self.conn.prepare(
            "SELECT id, stock_id, date, quantity, price_per_share, fees, notes
             FROM sell_transactions WHERE id = ?1",
        )?;

        let mut rows = stmt.query(params![id])?;

        if let Some(row) = rows.next()? {
            Ok(Some(SellTransaction {
                id: Some(row.get(0)?),
                stock_id: row.get(1)?,
                date: row.get::<_, String>(2)?.try_into().unwrap(),
                quantity: row.get(3)?,
                price_per_share: row.get(4)?,
                fees: row.get(5)?,
                notes: row.get(6)?,
            }))
        } else {
            Ok(None)
        }
    }

    /// Get all sell transactions for a specific stock
    pub fn find_by_stock_id(&self, stock_id: &str) -> Result<Vec<SellTransaction>> {
        let mut stmt = self.conn.prepare(
            "SELECT id, stock_id, date, quantity, price_per_share, fees, notes
             FROM sell_transactions
             WHERE stock_id = ?1
             ORDER BY date",
        )?;

        let tx_iter = stmt.query_map(params![stock_id], |row| {
            Ok(SellTransaction {
                id: Some(row.get(0)?),
                stock_id: row.get(1)?,
                date: row.get::<_, String>(2)?.try_into().unwrap(),
                quantity: row.get(3)?,
                price_per_share: row.get(4)?,
                fees: row.get(5)?,
                notes: row.get(6)?,
            })
        })?;

        let mut transactions = Vec::new();
        for tx in tx_iter {
            transactions.push(tx?);
        }

        Ok(transactions)
    }

    /// Get all sell transactions in a specific financial year
    pub fn find_by_financial_year(
        &self,
        start_year: u32,
        end_year: u32,
    ) -> Result<Vec<SellTransaction>> {
        let mut stmt = self.conn.prepare(
            "SELECT id, stock_id, date, quantity, price_per_share, fees, notes
             FROM sell_transactions
             WHERE
                (strftime('%Y', date) = ?1 AND strftime('%m', date) >= '07') OR
                (strftime('%Y', date) = ?2 AND strftime('%m', date) <= '06')
             ORDER BY date",
        )?;

        let tx_iter = stmt.query_map(
            params![start_year.to_string(), end_year.to_string()],
            |row| {
                Ok(SellTransaction {
                    id: Some(row.get(0)?),
                    stock_id: row.get(1)?,
                    date: row.get::<_, String>(2)?.try_into().unwrap(),
                    quantity: row.get(3)?,
                    price_per_share: row.get(4)?,
                    fees: row.get(5)?,
                    notes: row.get(6)?,
                })
            },
        )?;

        let mut transactions = Vec::new();
        for tx in tx_iter {
            transactions.push(tx?);
        }

        Ok(transactions)
    }

    /// Get all sell transactions
    pub fn get_all(&self) -> Result<Vec<SellTransaction>> {
        let mut stmt = self.conn.prepare(
            "SELECT id, stock_id, date, quantity, price_per_share, fees, notes
             FROM sell_transactions
             ORDER BY date",
        )?;

        let tx_iter = stmt.query_map([], |row| {
            Ok(SellTransaction {
                id: Some(row.get(0)?),
                stock_id: row.get(1)?,
                date: row.get::<_, String>(2)?.try_into().unwrap(),
                quantity: row.get(3)?,
                price_per_share: row.get(4)?,
                fees: row.get(5)?,
                notes: row.get(6)?,
            })
        })?;

        let mut transactions = Vec::new();
        for tx in tx_iter {
            transactions.push(tx?);
        }

        Ok(transactions)
    }
}

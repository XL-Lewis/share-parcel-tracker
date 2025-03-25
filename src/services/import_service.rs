use anyhow::{bail, Result};
use csv::ReaderBuilder;
use rusqlite::Connection;
use std::fs::File;

use crate::date::Date;
use crate::services::{AllocationService, StockService, TransactionService};

/// Service for importing data from external sources
pub struct ImportService<'a> {
    conn: &'a Connection,
}

impl<'a> ImportService<'a> {
    /// Create a new ImportService with a database connection
    pub fn new(conn: &'a Connection) -> Self {
        Self { conn }
    }

    /// Import transactions from a CSV file
    pub fn import_csv_data(&self, file_path: &str) -> Result<u32> {
        // Open the CSV file
        let file = File::open(file_path)?;
        let mut reader = ReaderBuilder::new()
            .has_headers(true)
            .trim(csv::Trim::All)
            .from_reader(file);

        let stock_service = StockService::new(self.conn);
        let transaction_service = TransactionService::new(self.conn);
        let allocation_service = AllocationService::new(self.conn);

        let mut transaction_count = 0;

        // Process each record
        for result in reader.records() {
            let record = result?;

            // Extract and parse the fields
            if record.len() < 4 {
                bail!("Skipping invalid record, insufficient fields: {:?}", record);
            }

            // Parse date from DD/MMM/YY format in CSV to YYYY-MM-DD
            let date: Date = Date::from_csv(&record[0])?;

            let symbol = record[1].trim().to_string();
            let shares_str = record[2].trim();

            // Clean up price string (remove $ and handle incomplete decimals)
            let mut price_str = record[3].trim().to_string();
            price_str = price_str.replace("$", ""); // Remove dollar sign

            // Handle prices like "3." (incomplete decimal)
            if price_str.ends_with(".") {
                price_str = price_str + "0";
            }

            // Handle prices like ".0105" (missing leading zero)
            if price_str.starts_with(".") {
                price_str = "0".to_string() + &price_str;
            }

            // Parse shares
            let shares: i32 = match shares_str.parse() {
                Ok(val) => val,
                Err(e) => {
                    bail!("Invalid shares value '{}': {}", shares_str, e);
                }
            };

            // Parse price
            let price_per_share: f64 = match price_str.parse() {
                Ok(val) => val,
                Err(e) => {
                    bail!(
                        "Invalid price value '{}' (original: '{}'): {}",
                        price_str,
                        record[3].trim(),
                        e
                    );
                }
            };

            // Default fees - could be customized or added to CSV
            let fees = 9.5;

            // Ensure stock exists in stocks table
            stock_service.ensure_stock_exists(&symbol)?;

            // Determine if this is a buy or sell transaction based on shares value
            if shares > 0 {
                // This is a buy transaction
                transaction_service.add_buy_transaction(
                    &symbol,
                    date,
                    shares as u32,
                    price_per_share,
                    fees,
                    Some("Imported from CSV".to_string()),
                )?;
            } else if shares < 0 {
                // This is a sell transaction (negative shares means selling)
                let sell_id = transaction_service.add_sell_transaction(
                    &symbol,
                    date,
                    shares.abs() as u32,
                    price_per_share,
                    fees,
                    Some("Imported from CSV".to_string()),
                )?;

                // Allocate sell transaction to buy transactions using FIFO
                allocation_service.allocate_sell_transaction_fifo(sell_id as i32)?;
            } else {
                // Zero shares - skip
                bail!("Skipping record with zero shares: {:?}", record);
            }

            transaction_count += 1;
        }

        Ok(transaction_count)
    }
}

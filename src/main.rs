mod seed;
mod utils;
use chrono::prelude::*;
use csv::ReaderBuilder;
use rusqlite::{params, Connection, Result};
use seed::insert_sample_data;
use std::collections::HashMap;
use std::error::Error;
use std::fs::File;
use std::path::Path;
use utils::*;

#[derive(Debug)]
struct BuyTransaction {
    id: i32,
    stock_id: String,
    date: String,
    quantity: i32,
    price_per_share: f64,
    fees: f64,
    notes: Option<String>,
}

#[derive(Debug)]
struct SellTransaction {
    id: i32,
    stock_id: String,
    date: String,
    quantity: i32,
    price_per_share: f64,
    fees: f64,
    linked_buy_id: Option<i32>, // Reference to the buy transaction
    notes: Option<String>,
}

#[derive(Debug)]
struct StockSummary {
    symbol: String,
    name: String,
    total_owned: i32,
    average_buy_price: f64,
    current_value: f64,
}

fn main() -> Result<()> {
    // Create a connection to an SQLite database file
    let db_path = Path::new("shares.db");
    let conn = Connection::open(db_path)?;

    println!("Connected to SQLite database");

    println!("Dropping tables");
    drop_tables(&conn)?;

    // Create tables for our share tracking system
    create_tables(&conn)?;
    println!("Created database tables");

    // Import transactions from CSV
    match import_csv_data(&conn, "transactions.csv") {
        Ok(count) => println!("Imported {} transactions from CSV", count),
        Err(e) => eprintln!("Error importing CSV: {}", e),
    }

    // List all transactions
    print_transactions(&conn)?;

    Ok(())
}

fn create_tables(conn: &Connection) -> Result<()> {
    // Create buy transactions table
    conn.execute(
        "CREATE TABLE IF NOT EXISTS buy_transactions (
            id INTEGER PRIMARY KEY,
            stock_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            price_per_share REAL NOT NULL,
            fees REAL NOT NULL,
            notes TEXT
        )",
        [],
    )?;

    // Create sell transactions table
    conn.execute(
        "CREATE TABLE IF NOT EXISTS sell_transactions (
            id INTEGER PRIMARY KEY,
            stock_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            price_per_share REAL NOT NULL,
            fees REAL NOT NULL,
            linked_buy_id INTEGER,
            notes TEXT,
            FOREIGN KEY (linked_buy_id) REFERENCES buy_transactions (id)
        )",
        [],
    )?;

    Ok(())
}

fn drop_tables(conn: &Connection) -> Result<()> {
    conn.execute("PRAGMA foreign_keys = OFF", [])?;
    conn.execute("DROP TABLE IF EXISTS sell_transactions", [])?;
    conn.execute("DROP TABLE IF EXISTS buy_transactions", [])?;
    conn.execute("PRAGMA foreign_keys = ON", [])?;
    Ok(())
}

fn import_csv_data(
    conn: &Connection,
    file_path: &str,
) -> std::result::Result<usize, Box<dyn Error>> {
    // Open the CSV file
    let file = File::open(file_path)?;
    let mut reader = ReaderBuilder::new()
        .has_headers(true)
        .trim(csv::Trim::All)
        .from_reader(file);

    let mut transaction_count = 0;

    // Process each record
    for result in reader.records() {
        let record = result?;

        // Extract and parse the fields
        if record.len() < 4 {
            eprintln!(
                "Warning: Skipping invalid record, insufficient fields: {:?}",
                record
            );
            continue;
        }

        // Parse date (convert from DD/MMM/YY to YYYY-MM-DD)
        let chrono_date = crate::utils::date_string_to_unix_i64(record[0].trim())?;

        let stock_id = record[1].trim().to_string();
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
                eprintln!("Warning: Invalid shares value '{}': {}", shares_str, e);
                continue;
            }
        };

        // Parse price
        let price_per_share: f64 = match price_str.parse() {
            Ok(val) => val,
            Err(e) => {
                eprintln!(
                    "Warning: Invalid price value '{}' (original: '{}'): {}",
                    price_str,
                    record[3].trim(),
                    e
                );
                continue;
            }
        };

        // Default fees - could be customized or added to CSV
        let fees = 9.5;

        // Determine if this is a buy or sell transaction based on shares value
        if shares > 0 {
            // This is a buy transaction
            conn.execute(
                "INSERT INTO buy_transactions (stock_id, date, quantity, price_per_share, fees, notes)
                 VALUES (?1, ?2, ?3, ?4, ?5, ?6)",
                params![
                    stock_id,
                    chrono_date,
                    shares,
                    price_per_share,
                    fees,
                    format!("Imported from CSV")
                ],
            )?;
        } else if shares < 0 {
            // This is a sell transaction (negative shares means selling)
            conn.execute(
                "INSERT INTO sell_transactions (stock_id, date, quantity, price_per_share, fees, notes)
                 VALUES (?1, ?2, ?3, ?4, ?5, ?6)",
                params![
                    stock_id,
                    chrono_date,
                    shares.abs(), // Use absolute value for quantity
                    price_per_share,
                    fees,
                    format!("Imported from CSV")
                ],
            )?;
        } else {
            // Zero shares - skip
            eprintln!("Warning: Skipping record with zero shares: {:?}", record);
            continue;
        }

        transaction_count += 1;
    }

    Ok(transaction_count)
}

fn print_transactions(conn: &Connection) -> Result<()> {
    println!("\n--- BUY TRANSACTIONS ---");
    println!(
        "{:<5} {:<8} {:<12} {:<8} {:<15} {:<8} {:<20}",
        "ID", "STOCK", "DATE", "QTY", "PRICE/SHARE", "FEES", "NOTES"
    );

    let mut stmt = conn.prepare(
        "SELECT id, stock_id, date, quantity, price_per_share, fees, notes
         FROM buy_transactions
         ORDER BY date",
    )?;

    let buy_iter = stmt.query_map([], |row| {
        Ok(BuyTransaction {
            id: row.get(0)?,
            stock_id: row.get(1)?,
            date: row.get(2)?,
            quantity: row.get(3)?,
            price_per_share: row.get(4)?,
            fees: row.get(5)?,
            notes: row.get(6)?,
        })
    })?;

    for buy in buy_iter {
        let buy = buy?;
        println!(
            "{:<5} {:<8} {:<12} {:<8} ${:<14.2} ${:<7.2} {}",
            buy.id,
            buy.stock_id,
            date_unix_i64_into_string(buy.date.parse().unwrap()),
            buy.quantity,
            buy.price_per_share,
            buy.fees,
            buy.notes.unwrap_or_default()
        );
    }

    println!("\n--- SELL TRANSACTIONS ---");
    println!(
        "{:<5} {:<8} {:<12} {:<8} {:<15} {:<8} {:<12} {:<20}",
        "ID", "STOCK", "DATE", "QTY", "PRICE/SHARE", "FEES", "LINKED BUY", "NOTES"
    );

    let mut stmt = conn.prepare(
        "SELECT id, stock_id, date, quantity, price_per_share, fees, linked_buy_id, notes
         FROM sell_transactions
         ORDER BY date",
    )?;

    let sell_iter = stmt.query_map([], |row| {
        Ok(SellTransaction {
            id: row.get(0)?,
            stock_id: row.get(1)?,
            date: row.get(2)?,
            quantity: row.get(3)?,
            price_per_share: row.get(4)?,
            fees: row.get(5)?,
            linked_buy_id: row.get(6)?,
            notes: row.get(7)?,
        })
    })?;

    for sell in sell_iter {
        let sell = sell?;
        println!(
            "{:<5} {:<8} {:<12} {:<8} ${:<14.2} ${:<7.2} {:<12} {}",
            sell.id,
            sell.stock_id,
            date_unix_i64_into_string(sell.date.parse().unwrap()),
            sell.quantity,
            sell.price_per_share,
            sell.fees,
            sell.linked_buy_id
                .map_or("N/A".to_string(), |id| id.to_string()),
            sell.notes.unwrap_or_default()
        );
    }

    Ok(())
}

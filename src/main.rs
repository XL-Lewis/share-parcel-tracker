mod date;

use anyhow::Result;
use csv::ReaderBuilder;
use date::*;
use rusqlite::{params, Connection};
use std::collections::HashMap;
use std::fs::File;
use std::path::Path;

#[derive(Debug)]
struct Stock {
    id: Option<i32>,
    symbol: String,
}

#[derive(Debug)]
struct BuyTransaction {
    id: Option<i32>,
    stock_id: String,
    date: Date,
    quantity: u32,
    price_per_share: f64,
    fees: f64,
    notes: Option<String>,
}

#[derive(Debug)]
struct SellTransaction {
    id: Option<i32>,
    stock_id: String,
    date: Date,
    quantity: u32,
    price_per_share: f64,
    fees: f64,
    notes: Option<String>,
}

#[derive(Debug)]
struct SellAllocation {
    id: Option<i32>,
    sell_transaction_id: i32,
    buy_transaction_id: i32,
    quantity: u32,
    allocated_buy_price: f64,
    allocated_buy_fees: f64,
    capital_gain: f64,
    cgt_discount_applied: bool,
}

// Capital gains summary structure
#[derive(Debug)]
struct CapitalGainsSummary {
    financial_year: String,
    short_term_gains: f64, // Held < 1 year
    long_term_gains: f64,  // Held > 1 year (before discount)
    discounted_gains: f64, // After 50% discount
    capital_losses: f64,
    net_capital_gains: f64, // Total taxable
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

    // Print capital gains summary for current financial year
    print_capital_gains_summary(&conn, "2023-2024")?;

    // Print current holdings
    print_current_holdings(conn)?;
    Ok(())
}

// Generate capital gains summary for a specific financial year
fn generate_capital_gains_summary(conn: &Connection, fy: &str) -> Result<CapitalGainsSummary> {
    // Financial years in Australia are formatted as "2023-2024" for FY starting July 1, 2023
    let parts: Vec<&str> = fy.split('-').collect();
    let start_year: u32 = parts[0].parse()?;
    let end_year: u32 = parts[1].parse()?;

    // Query to get all sell allocations in the specified financial year
    // Our dates are stored as "DD-MM-YY" format, so we need to extract year and month carefully
    let mut stmt = conn.prepare(
        "SELECT sa.capital_gain, sa.cgt_discount_applied
         FROM sell_allocations sa
         JOIN sell_transactions st ON sa.sell_transaction_id = st.id
         WHERE
            (CAST(substr(st.date, 7, 2) AS INTEGER) + 2000 = ?1 AND CAST(substr(st.date, 4, 2) AS INTEGER) >= 7) OR
            (CAST(substr(st.date, 7, 2) AS INTEGER) + 2000 = ?2 AND CAST(substr(st.date, 4, 2) AS INTEGER) <= 6)"
    )?;

    println!("Querying capital gains for FY {}-{}", start_year, end_year);

    let rows = stmt.query_map(params![start_year, end_year], |row| {
        let capital_gain: f64 = row.get(0)?;
        let cgt_discount_applied: bool = row.get::<_, i32>(1)? != 0;

        Ok((capital_gain, cgt_discount_applied))
    })?;

    let mut short_term_gains = 0.0;
    let mut long_term_gains = 0.0;
    let mut capital_losses = 0.0;

    // Calculate gains and losses
    for row_result in rows {
        let (gain, discount_eligible) = row_result.map_err(|e| anyhow::anyhow!("{}", e))?;

        if gain > 0.0 {
            if discount_eligible {
                long_term_gains += gain;
            } else {
                short_term_gains += gain;
            }
        } else if gain < 0.0 {
            capital_losses += -gain; // Convert to positive for reporting
        }
    }

    // Apply 50% CGT discount to long-term gains
    let discounted_gains = long_term_gains * 0.5;

    // Calculate net capital gains (losses can offset gains)
    let total_gains = short_term_gains + discounted_gains;
    let net_capital_gains = if total_gains > capital_losses {
        total_gains - capital_losses
    } else {
        0.0 // Capital losses can only offset gains, excess is carried forward
    };

    Ok(CapitalGainsSummary {
        financial_year: fy.to_string(),
        short_term_gains,
        long_term_gains,
        discounted_gains,
        capital_losses,
        net_capital_gains,
    })
}

// Print capital gains summary
fn print_capital_gains_summary(conn: &Connection, fy: &str) -> Result<()> {
    println!("\n--- CAPITAL GAINS SUMMARY (FY {}) ---", fy);

    // First, print stock-specific summaries
    println!("\nPER-STOCK BREAKDOWN:");
    println!(
        "{:<8} {:<15} {:<15} {:<15} {:<15}",
        "STOCK", "SHORT-TERM", "LONG-TERM", "LOSSES", "NET GAINS"
    );

    // Parse financial year
    let parts: Vec<&str> = fy.split('-').collect();
    let start_year: u32 = parts[0].parse()?;
    let end_year: u32 = parts[1].parse()?;

    // Query to get capital gains per stock
    let mut stmt = conn.prepare(
        "SELECT
            bt.stock_id,
            SUM(CASE WHEN sa.capital_gain > 0 AND sa.cgt_discount_applied = 0 THEN sa.capital_gain ELSE 0 END) as short_term,
            SUM(CASE WHEN sa.capital_gain > 0 AND sa.cgt_discount_applied = 1 THEN sa.capital_gain ELSE 0 END) as long_term,
            SUM(CASE WHEN sa.capital_gain < 0 THEN -sa.capital_gain ELSE 0 END) as losses
         FROM sell_allocations sa
         JOIN buy_transactions bt ON sa.buy_transaction_id = bt.id
         JOIN sell_transactions st ON sa.sell_transaction_id = st.id
         WHERE
            (CAST(substr(st.date, 7, 2) AS INTEGER) + 2000 = ?1 AND CAST(substr(st.date, 4, 2) AS INTEGER) >= 7) OR
            (CAST(substr(st.date, 7, 2) AS INTEGER) + 2000 = ?2 AND CAST(substr(st.date, 4, 2) AS INTEGER) <= 6)
         GROUP BY bt.stock_id
         ORDER BY bt.stock_id"
    )?;

    let rows = stmt.query_map(params![start_year, end_year], |row| {
        let stock_id: String = row.get(0)?;
        let short_term: f64 = row.get(1)?;
        let long_term: f64 = row.get(2)?;
        let losses: f64 = row.get(3)?;

        // Calculate discounted and net gains for this stock
        let discounted = long_term * 0.5;
        let total = short_term + discounted;
        let net = if total > losses { total - losses } else { 0.0 };

        Ok((stock_id, short_term, long_term, losses, net))
    })?;

    for row_result in rows {
        let (stock_id, short_term, long_term, losses, net) = row_result?;

        println!(
            "{:<8} ${:<14.2} ${:<14.2} ${:<14.2} ${:<14.2}",
            stock_id, short_term, long_term, losses, net
        );
    }

    // Generate and print overall summary
    let summary = generate_capital_gains_summary(conn, fy)?;

    println!("\nOVERALL SUMMARY:");
    println!(
        "Short-term capital gains:   ${:.2}",
        summary.short_term_gains
    );
    println!(
        "Long-term capital gains:    ${:.2}",
        summary.long_term_gains
    );
    println!(
        "CGT 50% discount applied:   ${:.2}",
        summary.long_term_gains - summary.discounted_gains
    );
    println!(
        "Discounted gains:           ${:.2}",
        summary.discounted_gains
    );
    println!("Capital losses:             ${:.2}", summary.capital_losses);
    println!("----------------------------------------");
    println!(
        "Net capital gains (taxable): ${:.2}",
        summary.net_capital_gains
    );

    if summary.net_capital_gains == 0.0
        && summary.capital_losses > (summary.short_term_gains + summary.discounted_gains)
    {
        let excess_losses =
            summary.capital_losses - (summary.short_term_gains + summary.discounted_gains);
        println!("Carry-forward losses:       ${:.2}", excess_losses);
    }

    Ok(())
}

fn create_tables(conn: &Connection) -> Result<()> {
    // Enable foreign keys
    conn.execute("PRAGMA foreign_keys = ON", [])?;

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
            date TEXT NOT NULL,
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
            date TEXT NOT NULL,
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

fn drop_tables(conn: &Connection) -> Result<()> {
    conn.execute("PRAGMA foreign_keys = OFF", [])?;
    conn.execute("DROP TABLE IF EXISTS sell_allocations", [])?;
    conn.execute("DROP TABLE IF EXISTS sell_transactions", [])?;
    conn.execute("DROP TABLE IF EXISTS buy_transactions", [])?;
    conn.execute("DROP TABLE IF EXISTS stocks", [])?;
    conn.execute("PRAGMA foreign_keys = ON", [])?;
    Ok(())
}

fn import_csv_data(conn: &Connection, file_path: &str) -> Result<u32> {
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
        let date: Date = Date::from_csv(record[0].to_string())?;

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

        // Ensure stock exists in stocks table
        conn.execute(
            "INSERT OR IGNORE INTO stocks (symbol) VALUES (?1)",
            params![symbol],
        )?;

        // Determine if this is a buy or sell transaction based on shares value
        if shares > 0 {
            // This is a buy transaction
            conn.execute(
                "INSERT INTO buy_transactions (stock_id, date, quantity, price_per_share, fees, notes)
                VALUES (?1, ?2, ?3, ?4, ?5, ?6)",
                params![
                    symbol,
                    date.to_string(),
                    shares as u32,
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
                    symbol,
                    date.to_string(),
                    shares.abs() as u32, // Use absolute value for quantity
                    price_per_share,
                    fees,
                    format!("Imported from CSV")
                ],
            )?;

            // Get the ID of the most recently inserted row
            let sell_id = conn.last_insert_rowid();

            // Allocate sell transaction to buy transactions using FIFO
            allocate_sell_transaction_fifo(conn, sell_id as i32)?;
        } else {
            // Zero shares - skip
            eprintln!("Warning: Skipping record with zero shares: {:?}", record);
            continue;
        }

        transaction_count += 1;
    }

    Ok(transaction_count)
}

// FIFO allocation function to link sell transactions to buy transactions
fn allocate_sell_transaction_fifo(conn: &Connection, sell_transaction_id: i32) -> Result<()> {
    // Check if this sell transaction already has allocations
    let existing_count: i64 = conn.query_row(
        "SELECT COUNT(*) FROM sell_allocations WHERE sell_transaction_id = ?1",
        params![sell_transaction_id],
        |row| row.get(0),
    )?;

    if existing_count > 0 {
        // This transaction already has allocations, skip to avoid duplicates
        return Ok(());
    }

    // Get sell transaction details
    let sell_transaction = conn.query_row(
        "SELECT id, stock_id, date, quantity, price_per_share, fees FROM sell_transactions WHERE id = ?1",
        params![sell_transaction_id],
        |row| {
            Ok(SellTransaction {
                id: Some(row.get(0)?),
                stock_id: row.get(1)?,
                date: row.get::<usize, String>(2)?.try_into().unwrap(),
                quantity: row.get(3)?,
                price_per_share: row.get(4)?,
                fees: row.get(5)?,
                notes: None,
            })
        },
    )?;

    // Get all buy transactions for this stock with remaining quantity
    let mut stmt = conn.prepare(
        "SELECT bt.id, bt.date, bt.quantity, bt.price_per_share, bt.fees,
         (SELECT COALESCE(SUM(sa.quantity), 0) FROM sell_allocations sa WHERE sa.buy_transaction_id = bt.id) as allocated
         FROM buy_transactions bt
         WHERE bt.stock_id = ?1
         ORDER BY
            CAST(substr(bt.date, 7, 2) AS INTEGER), -- Year
            CAST(substr(bt.date, 4, 2) AS INTEGER), -- Month
            CAST(substr(bt.date, 1, 2) AS INTEGER)" // FIFO - oldest first by date components
    )?;

    // Get all buy transactions for this stock
    let mut buy_txs = Vec::new();

    let rows = stmt.query_map(params![sell_transaction.stock_id], |row| {
        let id: i32 = row.get(0)?;
        let date_str: String = row.get(1)?;
        let quantity: u32 = row.get(2)?;
        let price_per_share: f64 = row.get(3)?;
        let fees: f64 = row.get(4)?;
        let allocated: u32 = row.get(5)?;
        let remaining = quantity - allocated;

        Ok((
            id,
            date_str.try_into().unwrap(), // Convert to Date
            quantity,
            remaining,
            price_per_share,
            fees,
        ))
    })?;

    // Convert from rusqlite::Error to anyhow::Error
    for row_result in rows {
        buy_txs.push(row_result.map_err(|e| anyhow::anyhow!("{}", e))?);
    }

    let mut remaining_to_allocate = sell_transaction.quantity;

    for (buy_id, buy_date, total_quantity, remaining_quantity, buy_price, buy_fees) in buy_txs {
        if remaining_to_allocate == 0 {
            break;
        }

        if remaining_quantity == 0 {
            continue; // Skip if no remaining quantity
        }

        // Calculate allocation quantity
        let allocation_quantity = std::cmp::min(remaining_to_allocate, remaining_quantity);

        // Calculate proportions
        let proportion = allocation_quantity as f64 / total_quantity as f64;

        // Calculate allocated amounts
        let allocated_buy_price = buy_price * allocation_quantity as f64;
        let allocated_buy_fees = buy_fees * proportion;

        // Calculate proportional sell amount and fees
        let allocated_sell_price = sell_transaction.price_per_share * allocation_quantity as f64;
        let allocated_sell_fees =
            sell_transaction.fees * (allocation_quantity as f64 / sell_transaction.quantity as f64);

        // Calculate capital gain/loss
        let cost_basis = allocated_buy_price + allocated_buy_fees;
        let proceeds = allocated_sell_price - allocated_sell_fees;
        let capital_gain = proceeds - cost_basis;

        // Check if CGT discount applies (held for more than 1 year)
        let cgt_discount_applied = is_eligible_for_cgt_discount(&buy_date, &sell_transaction.date);

        // Create allocation record
        conn.execute(
            "INSERT INTO sell_allocations (
                sell_transaction_id, buy_transaction_id, quantity,
                allocated_buy_price, allocated_buy_fees,
                capital_gain, cgt_discount_applied
            ) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)",
            params![
                sell_transaction_id,
                buy_id,
                allocation_quantity,
                allocated_buy_price,
                allocated_buy_fees,
                capital_gain,
                if cgt_discount_applied { 1 } else { 0 }
            ],
        )?;

        // Update remaining to allocate
        remaining_to_allocate -= allocation_quantity;
    }

    // Check if we've allocated all shares
    if remaining_to_allocate > 0 {
        eprintln!(
            "Warning: Could not allocate all shares for sell transaction {}: {} remaining",
            sell_transaction_id, remaining_to_allocate
        );
    }

    Ok(())
}

// Check if a transaction is eligible for CGT discount (held for more than 1 year)
fn is_eligible_for_cgt_discount(buy_date: &Date, sell_date: &Date) -> bool {
    // For simplicity, just check if the years differ by more than 1,
    // or if they differ by exactly 1 and the sell month/day is greater than or equal to buy month/day
    if sell_date.year > buy_date.year + 1 {
        return true;
    } else if sell_date.year == buy_date.year + 1 {
        return (sell_date.month > buy_date.month)
            || (sell_date.month == buy_date.month && sell_date.day >= buy_date.day);
    }
    false
}

fn get_current_holdings(conn: &Connection) -> Result<HashMap<String, u32>> {
    let mut holdings: HashMap<String, u32> = HashMap::new();

    // Get buy transactions
    let mut stmt = conn.prepare("SELECT stock_id, quantity FROM buy_transactions")?;

    let buy_txns = stmt.query_map([], |row| {
        Ok((row.get::<usize, String>(0)?, row.get::<usize, u32>(1)?))
    })?;

    // Add all buy transactions to holdings
    for txn in buy_txns {
        let (stock_id, quantity) = txn?;
        *holdings.entry(stock_id).or_insert(0) += quantity;
    }

    // Get sell transactions
    let mut stmt = conn.prepare("SELECT stock_id, quantity FROM sell_transactions")?;

    let sell_txns = stmt.query_map([], |row| {
        Ok((row.get::<usize, String>(0)?, row.get::<usize, u32>(1)?))
    })?;

    // Subtract all sell transactions from holdings
    for txn in sell_txns {
        let (stock_id, quantity) = txn?;
        *holdings.entry(stock_id).or_insert(0) -= quantity;
    }

    Ok(holdings)
}

fn print_current_holdings(conn: Connection) -> Result<()> {
    println!("\n--- Current Holdings ---");

    println!("{:<8} {:<8}", "STOCK", "QTY");
    let current_holdings = get_current_holdings(&conn)?;

    // Display only stocks with positive holdings
    current_holdings
        .iter()
        .filter(|(_, &qty)| qty > 0)
        .for_each(|(stock, qty)| {
            println!("{:<8} {:<8}", stock, qty);
        });

    Ok(())
}

fn print_transactions(conn: &Connection) -> Result<()> {
    println!("\n--- BUY TRANSACTIONS ---");
    println!(
        "{:<5} {:<8} {:<12} {:<8} {:<15} {:<8} {:<20}",
        "ID", "STOCK", "DATE", "QTY", "PRICE/SHARE", "FEES", "NOTES"
    );

    // Query buy transactions - order chronologically by date components in DD-MM-YY format
    let mut stmt = conn.prepare(
        "SELECT id, stock_id, date, quantity, price_per_share, fees, notes
        FROM buy_transactions
        ORDER BY
            CAST(substr(date, 7, 2) AS INTEGER), -- Year
            CAST(substr(date, 4, 2) AS INTEGER), -- Month
            CAST(substr(date, 1, 2) AS INTEGER)  -- Day",
    )?;

    let buy_iter = stmt.query_map([], |row| {
        Ok(BuyTransaction {
            id: Some(row.get(0)?),
            stock_id: row.get(1)?,
            date: row.get::<usize, String>(2)?.try_into().unwrap(),
            quantity: row.get(3)?,
            price_per_share: row.get(4)?,
            fees: row.get(5)?,
            notes: row.get(6)?,
        })
    })?;

    let mut old_date = Date {
        year: 2000,
        day: 0,
        month: 6,
    };

    for buy in buy_iter {
        let buy = buy?;
        // Check if we're entering a new financial year
        if old_date.year > 0 && Date::which_fy(&old_date) != Date::which_fy(&buy.date) {
            let fy_start = 2000 + Date::which_fy(&buy.date);
            println!(
                "------- New Financial Year: {}-{} -------",
                fy_start,
                fy_start + 1
            );
        }
        println!(
            "{:<5} {:<8} {:<12} {:<8} ${:<14.2} ${:<7.2} {}",
            buy.id.unwrap_or(0),
            buy.stock_id,
            buy.date,
            buy.quantity,
            buy.price_per_share,
            buy.fees,
            buy.notes.unwrap_or_default()
        );
        old_date = buy.date;
    }

    println!("\n--- SELL TRANSACTIONS ---");
    println!(
        "{:<5} {:<8} {:<12} {:<8} {:<15} {:<8} {:<20}",
        "ID", "STOCK", "DATE", "QTY", "PRICE/SHARE", "FEES", "NOTES"
    );

    // Query sell transactions - order chronologically by date components in DD-MM-YY format
    let mut stmt = conn.prepare(
        "SELECT id, stock_id, date, quantity, price_per_share, fees, notes
         FROM sell_transactions
         ORDER BY
            CAST(substr(date, 7, 2) AS INTEGER), -- Year
            CAST(substr(date, 4, 2) AS INTEGER), -- Month
            CAST(substr(date, 1, 2) AS INTEGER)  -- Day",
    )?;

    let sell_iter = stmt.query_map([], |row| {
        Ok(SellTransaction {
            id: Some(row.get(0)?),
            stock_id: row.get(1)?,
            date: row.get::<usize, String>(2)?.try_into().unwrap(),
            quantity: row.get(3)?,
            price_per_share: row.get(4)?,
            fees: row.get(5)?,
            notes: row.get(6)?,
        })
    })?;

    old_date = Date {
        year: 2000,
        day: 0,
        month: 6,
    };

    for sell in sell_iter {
        let sell = sell?;
        // Check if we're entering a new financial year
        if old_date.year > 0 && Date::which_fy(&old_date) != Date::which_fy(&sell.date) {
            let fy_start = 2000 + Date::which_fy(&sell.date);
            println!(
                "------- New Financial Year: {}-{} -------",
                fy_start,
                fy_start + 1
            );
        }

        println!(
            "{:<5} {:<8} {:<12} {:<8} ${:<14.2} ${:<7.2} {}",
            sell.id.unwrap_or(0),
            sell.stock_id,
            sell.date,
            sell.quantity,
            sell.price_per_share,
            sell.fees,
            sell.notes.unwrap_or_default()
        );
        old_date = sell.date;
    }

    // Print sell allocations
    println!("\n--- SELL ALLOCATIONS ---");
    println!(
        "{:<5} {:<12} {:<12} {:<8} {:<8} {:<15} {:<12} {:<10}",
        "ID",
        "SELL TX ID",
        "BUY TX ID",
        "STOCK",
        "QTY",
        "CAPITAL GAIN",
        "BUY PRICE",
        "CGT DISCOUNT"
    );

    let mut stmt = conn.prepare(
        "SELECT sa.id, sa.sell_transaction_id, sa.buy_transaction_id, 
         bt.stock_id, sa.quantity, sa.allocated_buy_price, 
         sa.allocated_buy_fees, sa.capital_gain, sa.cgt_discount_applied
         FROM sell_allocations sa
         JOIN buy_transactions bt ON sa.buy_transaction_id = bt.id
         ORDER BY bt.stock_id, sa.sell_transaction_id",
    )?;

    let alloc_iter = stmt.query_map([], |row| {
        Ok((
            row.get::<_, i32>(0)?,      // id
            row.get::<_, i32>(1)?,      // sell_transaction_id
            row.get::<_, i32>(2)?,      // buy_transaction_id
            row.get::<_, String>(3)?,   // stock_id
            row.get::<_, u32>(4)?,      // quantity
            row.get::<_, f64>(5)?,      // allocated_buy_price
            row.get::<_, f64>(6)?,      // allocated_buy_fees
            row.get::<_, f64>(7)?,      // capital_gain
            row.get::<_, i32>(8)? != 0, // cgt_discount_applied
        ))
    })?;

    for alloc_result in alloc_iter {
        let (id, sell_id, buy_id, stock_id, qty, buy_price, buy_fees, gain, discount) =
            alloc_result?;
        println!(
            "{:<5} {:<12} {:<12} {:<8} {:<8} ${:<14.2} ${:<11.2} {}",
            id,
            sell_id,
            buy_id,
            stock_id,
            qty,
            gain,
            buy_price,
            if discount { "Yes" } else { "No" }
        );
    }

    Ok(())
}

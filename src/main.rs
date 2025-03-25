mod date;
mod db;
mod models;
mod repositories;
mod services;
mod ui;

use anyhow::Result;
use std::path::Path;

use db::create_connection;
use db::{create_tables, drop_tables};
use services::{ImportService, PortfolioService, ReportingService, TransactionService};
use ui::{PortfolioPrinter, ReportsPrinter, TransactionFormatter};

fn main() -> Result<()> {
    // Create a connection to an SQLite database file
    let db_path = Path::new("shares.db");
    let conn = create_connection(db_path)?;

    println!("Connected to SQLite database");

    println!("Dropping tables");
    drop_tables(&conn)?;

    // Create tables for our share tracking system
    create_tables(&conn)?;
    println!("Created database tables");

    // Import transactions from CSV
    let import_service = ImportService::new(&conn);
    match import_service.import_csv_data("transactions.csv") {
        Ok(count) => println!("Imported {} transactions from CSV", count),
        Err(e) => eprintln!("Error importing CSV: {}", e),
    }

    // List all transactions
    print_transactions(&conn)?;

    // Print capital gains summary for current financial year
    print_capital_gains_summary(&conn, "2023-2024")?;

    // Print current holdings
    print_current_holdings(&conn)?;

    Ok(())
}

/// Print all transactions from the database
fn print_transactions(conn: &rusqlite::Connection) -> Result<()> {
    let transaction_service = TransactionService::new(conn);

    // Get all transactions
    let buy_transactions = transaction_service.get_all_buy_transactions()?;
    let sell_transactions = transaction_service.get_all_sell_transactions()?;

    // Print transactions
    TransactionFormatter::print_buy_transactions(&buy_transactions);
    TransactionFormatter::print_sell_transactions(&sell_transactions);

    // For sell allocations, we need to get stock IDs too
    // This would be better handled via a join in the repository in a real app
    let mut buy_stock_map = Vec::new();
    for tx in &buy_transactions {
        if let Some(id) = tx.id {
            buy_stock_map.push((id, tx.stock_id.clone()));
        }
    }

    // Get all allocations
    let alloc_service = services::AllocationService::new(conn);
    let allocations = alloc_service.get_all_allocations()?;

    // Print allocations
    TransactionFormatter::print_sell_allocations(&allocations, &buy_stock_map);

    Ok(())
}

/// Print capital gains summary
fn print_capital_gains_summary(conn: &rusqlite::Connection, fy: &str) -> Result<()> {
    let reporting_service = ReportingService::new(conn);

    // Generate and print overall summary
    let summary = reporting_service.generate_capital_gains_summary(fy)?;
    ReportsPrinter::print_capital_gains_summary(&summary);

    // Generate and print per-stock breakdown
    let per_stock_gains = reporting_service.generate_capital_gains_by_stock(fy)?;
    ReportsPrinter::print_capital_gains_by_stock(fy, &per_stock_gains);

    Ok(())
}

/// Print current holdings
fn print_current_holdings(conn: &rusqlite::Connection) -> Result<()> {
    let portfolio_service = PortfolioService::new(conn);
    let holdings = portfolio_service.get_active_holdings()?;

    PortfolioPrinter::print_holdings(&holdings);

    Ok(())
}

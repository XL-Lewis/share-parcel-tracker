use crate::date::Date;
use crate::models::{BuyTransaction, SellAllocation, SellTransaction};

/// Handles formatting transactions for display
pub struct TransactionFormatter;

impl TransactionFormatter {
    /// Print a table of buy transactions
    pub fn print_buy_transactions(transactions: &[BuyTransaction]) {
        println!("\n--- BUY TRANSACTIONS ---");
        println!(
            "{:<5} {:<8} {:<12} {:<8} {:<15} {:<8} {:<20}",
            "ID", "STOCK", "DATE", "QTY", "PRICE/SHARE", "FEES", "NOTES"
        );

        let mut old_date = Date::dummy();

        for buy in transactions {
            // Check if we're entering a new financial year
            if old_date.year() > 0 && Date::which_fy(&old_date) != Date::which_fy(&buy.date) {
                let fy_start = Date::which_fy(&buy.date);
                println!(
                    "------- New Financial Year: {} -------",
                    Date::format_fy(fy_start)
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
                buy.notes.as_ref().unwrap_or(&String::new())
            );

            old_date = buy.date.clone();
        }
    }

    /// Print a table of sell transactions
    pub fn print_sell_transactions(transactions: &[SellTransaction]) {
        println!("\n--- SELL TRANSACTIONS ---");
        println!(
            "{:<5} {:<8} {:<12} {:<8} {:<15} {:<8} {:<20}",
            "ID", "STOCK", "DATE", "QTY", "PRICE/SHARE", "FEES", "NOTES"
        );

        let mut old_date = Date::dummy();

        for sell in transactions {
            // Check if we're entering a new financial year
            if old_date.year() > 0 && Date::which_fy(&old_date) != Date::which_fy(&sell.date) {
                let fy_start = Date::which_fy(&sell.date);
                println!(
                    "------- New Financial Year: {} -------",
                    Date::format_fy(fy_start)
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
                sell.notes.as_ref().unwrap_or(&String::new())
            );

            old_date = sell.date.clone();
        }
    }

    /// Print a table of sell allocations
    pub fn print_sell_allocations(allocations: &[SellAllocation], stock_map: &[(i32, String)]) {
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

        for alloc in allocations {
            // Find the stock symbol for this allocation
            let stock_id = stock_map
                .iter()
                .find(|(id, _)| *id == alloc.buy_transaction_id)
                .map(|(_, symbol)| symbol.clone())
                .unwrap_or_else(|| "N/A".to_string());

            println!(
                "{:<5} {:<12} {:<12} {:<8} {:<8} ${:<14.2} ${:<11.2} {}",
                alloc.id.unwrap_or(0),
                alloc.sell_transaction_id,
                alloc.buy_transaction_id,
                stock_id,
                alloc.quantity,
                alloc.capital_gain,
                alloc.allocated_buy_price,
                if alloc.cgt_discount_applied {
                    "Yes"
                } else {
                    "No"
                }
            );
        }
    }

    /// Format a financial value for display with dollar sign and two decimal places
    pub fn format_currency(value: f64) -> String {
        format!("${:.2}", value)
    }
}

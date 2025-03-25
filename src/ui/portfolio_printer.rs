use std::collections::HashMap;

/// Handles printing portfolio information
pub struct PortfolioPrinter;

impl PortfolioPrinter {
    /// Print the current holdings
    pub fn print_holdings(holdings: &HashMap<String, u32>) {
        println!("\n--- Current Holdings ---");
        println!("{:<8} {:<8}", "STOCK", "QTY");

        // Display only stocks with positive holdings, sorted by symbol
        let mut sorted_holdings: Vec<_> = holdings.iter().filter(|(_, &qty)| qty > 0).collect();

        sorted_holdings.sort_by(|a, b| a.0.cmp(b.0));

        for (stock, qty) in sorted_holdings {
            println!("{:<8} {:<8}", stock, qty);
        }
    }

    /// Print the valuation of the current holdings
    pub fn print_valuation(holdings: &HashMap<String, u32>, prices: &HashMap<String, f64>) {
        println!("\n--- Portfolio Valuation ---");
        println!(
            "{:<8} {:<8} {:<10} {:<12}",
            "STOCK", "QTY", "PRICE", "VALUE"
        );

        let mut total_value = 0.0;
        let mut sorted_holdings: Vec<_> = holdings.iter().filter(|(_, &qty)| qty > 0).collect();

        sorted_holdings.sort_by(|a, b| a.0.cmp(b.0));

        for (stock, qty) in sorted_holdings {
            let price = prices.get(stock).copied().unwrap_or(0.0);
            let value = price * (*qty as f64);
            total_value += value;

            println!("{:<8} {:<8} ${:<9.2} ${:<11.2}", stock, qty, price, value);
        }

        println!("----------------------------------------");
        println!("Total portfolio value:      ${:.2}", total_value);
    }

    /// Print a summary of the portfolio distribution by stock
    pub fn print_distribution(holdings: &HashMap<String, u32>, prices: &HashMap<String, f64>) {
        println!("\n--- Portfolio Distribution ---");
        println!("{:<8} {:<12} {:<10}", "STOCK", "VALUE", "PERCENTAGE");

        // Calculate total value
        let mut stock_values = HashMap::new();
        let mut total_value = 0.0;

        for (stock, qty) in holdings.iter().filter(|(_, &qty)| qty > 0) {
            let price = prices.get(stock).copied().unwrap_or(0.0);
            let value = price * (*qty as f64);
            stock_values.insert(stock, value);
            total_value += value;
        }

        // Display distribution
        let mut sorted_stocks: Vec<_> = stock_values.iter().collect();
        sorted_stocks.sort_by(|a, b| b.1.partial_cmp(a.1).unwrap_or(std::cmp::Ordering::Equal));

        for (stock, value) in sorted_stocks {
            let percentage = if total_value > 0.0 {
                (value / total_value) * 100.0
            } else {
                0.0
            };

            println!("{:<8} ${:<11.2} {:<9.2}%", stock, value, percentage);
        }
    }
}

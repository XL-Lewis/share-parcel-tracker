use crate::models::CapitalGainsSummary;

/// Handles printing financial reports
pub struct ReportsPrinter;

impl ReportsPrinter {
    /// Print the capital gains summary for a specific financial year
    pub fn print_capital_gains_summary(summary: &CapitalGainsSummary) {
        println!(
            "\n--- CAPITAL GAINS SUMMARY (FY {}) ---",
            summary.financial_year
        );

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

        // Check if there are excess losses to carry forward
        if summary.net_capital_gains == 0.0 {
            let excess_losses = summary.excess_losses();
            if excess_losses > 0.0 {
                println!("Carry-forward losses:       ${:.2}", excess_losses);
            }
        }
    }

    /// Print a per-stock breakdown of capital gains
    pub fn print_capital_gains_by_stock(fy: &str, stock_gains: &[(String, f64, f64, f64, f64)]) {
        println!("\nPER-STOCK BREAKDOWN (FY {}):", fy);
        println!(
            "{:<8} {:<15} {:<15} {:<15} {:<15}",
            "STOCK", "SHORT-TERM", "LONG-TERM", "LOSSES", "NET GAINS"
        );

        for (stock_id, short_term, long_term, losses, net) in stock_gains {
            println!(
                "{:<8} ${:<14.2} ${:<14.2} ${:<14.2} ${:<14.2}",
                stock_id, short_term, long_term, losses, net
            );
        }
    }

    /// Print a tax summary including income tax brackets
    pub fn print_tax_summary(summary: &CapitalGainsSummary, other_income: f64, tax_year: i32) {
        println!("\n--- TAX SUMMARY (FY {}) ---", summary.financial_year);

        // This is a simplified Australian tax calculation example
        // In a real app, this would need to be updated annually with correct tax brackets
        let total_taxable_income = other_income + summary.net_capital_gains;

        println!("Other income:               ${:.2}", other_income);
        println!(
            "Net capital gains:          ${:.2}",
            summary.net_capital_gains
        );
        println!("----------------------------------------");
        println!("Total taxable income:       ${:.2}", total_taxable_income);

        // Calculate tax (simplified example based on 2023-2024 Australian tax rates)
        let tax = Self::calculate_tax(total_taxable_income, tax_year);

        println!("Estimated tax payable:      ${:.2}", tax);
        println!(
            "Effective tax rate:         {:.2}%",
            (tax / total_taxable_income) * 100.0
        );
    }

    /// Calculate income tax (simplified Australian tax brackets for example)
    fn calculate_tax(income: f64, tax_year: i32) -> f64 {
        // This is a simplified version using 2023-2024 Australian tax brackets
        // In a real app, you would want to have different rates for different years
        // and potentially support different countries/jurisdictions

        // Example Australian 2023-2024 tax rates
        if income <= 18_200.0 {
            return 0.0;
        } else if income <= 45_000.0 {
            return (income - 18_200.0) * 0.19;
        } else if income <= 120_000.0 {
            return 5_092.0 + (income - 45_000.0) * 0.325;
        } else if income <= 180_000.0 {
            return 29_467.0 + (income - 120_000.0) * 0.37;
        } else {
            return 51_667.0 + (income - 180_000.0) * 0.45;
        }
    }
}

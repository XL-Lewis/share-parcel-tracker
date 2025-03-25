use anyhow::{bail, Error, Result};
use chrono::{Duration, NaiveDate};
use rusqlite::types::{FromSql, FromSqlError, FromSqlResult, ToSql, ToSqlOutput, ValueRef};
use std::convert::TryFrom;

/// Map month name abbreviation to month number
pub fn month_number(val: &str) -> Result<u32> {
    Ok(match val {
        "Jan" => 1,
        "Feb" => 2,
        "Mar" => 3,
        "Apr" => 4,
        "May" => 5,
        "Jun" => 6,
        "Jul" => 7,
        "Aug" => 8,
        "Sep" => 9,
        "Oct" => 10,
        "Nov" => 11,
        "Dec" => 12,
        _ => bail!("Tried to convert month, but [{val}] does not match mappings"),
    })
}

/// Represents a date in ISO format (YYYY-MM-DD) compatible with SQLite
#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord)]
pub struct Date(NaiveDate);

impl Date {
    /// Create a new Date from year, month, day
    pub fn new(year: i32, month: u32, day: u32) -> Result<Self> {
        let date = NaiveDate::from_ymd_opt(year, month, day)
            .ok_or_else(|| anyhow::anyhow!("Invalid date: {}-{}-{}", year, month, day))?;
        Ok(Date(date))
    }

    /// Parse a date from the CSV format (DD/MMM/YY)
    pub fn from_csv(date_str: &str) -> Result<Self> {
        let arr: Vec<&str> = date_str.split('/').collect();
        if arr.len() != 3 {
            bail!("Invalid date format: {}", date_str);
        }

        let day: u32 = arr[0].parse()?;
        let month: u32 = month_number(arr[1])?;
        let year_short: u32 = arr[2].parse()?;

        // Convert 2-digit year to 4-digit (assuming 20xx for any year)
        let year = 2000 + year_short;

        Self::new(year as i32, month, day)
    }

    /// Get the year component
    pub fn year(&self) -> i32 {
        // Access year directly from the wrapper NaiveDate
        let year_num = self.0.format("%Y").to_string().parse::<i32>().unwrap_or(0);
        year_num
    }

    /// Get the month component
    pub fn month(&self) -> u32 {
        // Access month directly from the wrapper NaiveDate
        let month_num = self.0.format("%m").to_string().parse::<u32>().unwrap_or(0);
        month_num
    }

    /// Get the day component
    pub fn day(&self) -> u32 {
        // Access day directly from the wrapper NaiveDate
        let day_num = self.0.format("%d").to_string().parse::<u32>().unwrap_or(0);
        day_num
    }

    /// Check if two dates are in different financial years
    pub fn in_different_fy(date1: &Date, date2: &Date) -> bool {
        let fy1 = Self::which_fy(date1);
        let fy2 = Self::which_fy(date2);
        fy1 != fy2
    }

    /// Returns the financial year that a particular date is set in
    /// This is the year that FY STARTED in
    /// i.e. july 1 2024 -> 2024
    /// jan 15 2024 -> 2023 (July 1, 2023 - June 30, 2024)
    pub fn which_fy(date: &Date) -> i32 {
        if date.month() >= 7 {
            date.year()
        } else {
            date.year() - 1
        }
    }

    /// Format the financial year as a string (e.g., "2023-2024")
    pub fn format_fy(fy_start_year: i32) -> String {
        format!("{}-{}", fy_start_year, fy_start_year + 1)
    }

    /// Check if a transaction is eligible for CGT discount (held for more than 1 year)
    pub fn is_eligible_for_cgt_discount(buy_date: &Date, sell_date: &Date) -> bool {
        // Use chrono's built-in date arithmetic
        let one_year_later = buy_date.0 + Duration::days(365);
        sell_date.0 > one_year_later
    }

    /// Get the underlying NaiveDate
    pub fn naive_date(&self) -> NaiveDate {
        self.0
    }

    /// Create a dummy date for initialization purposes
    pub fn dummy() -> Self {
        Self(NaiveDate::from_ymd_opt(2000, 6, 1).unwrap())
    }
}

/// Convert from string in ISO format (YYYY-MM-DD)
impl TryFrom<String> for Date {
    type Error = Error;

    fn try_from(date_str: String) -> Result<Self, Self::Error> {
        match NaiveDate::parse_from_str(&date_str, "%Y-%m-%d") {
            Ok(date) => Ok(Date(date)),
            Err(e) => bail!("Failed to parse date '{}': {}", date_str, e),
        }
    }
}

/// Display the date in ISO format (YYYY-MM-DD) for SQLite compatibility
impl std::fmt::Display for Date {
    fn fmt(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result {
        write!(f, "{}", self.0.format("%Y-%m-%d"))
    }
}

/// Implement ToSql for Date to store in SQLite
impl ToSql for Date {
    fn to_sql(&self) -> rusqlite::Result<ToSqlOutput<'_>> {
        let date_str = self.to_string();
        Ok(ToSqlOutput::from(date_str))
    }
}

/// Implement FromSql for Date to retrieve from SQLite
impl FromSql for Date {
    fn column_result(value: ValueRef<'_>) -> FromSqlResult<Self> {
        match value {
            ValueRef::Text(text) => {
                let text_str =
                    std::str::from_utf8(text).map_err(|e| FromSqlError::Other(Box::new(e)))?;

                NaiveDate::parse_from_str(text_str, "%Y-%m-%d")
                    .map_err(|e| FromSqlError::Other(Box::new(e)))
                    .map(|date| Date(date))
            }
            _ => Err(FromSqlError::InvalidType),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use rusqlite::{Connection, Result as SqliteResult};

    #[test]
    fn test_month_number() {
        // Test all valid month abbreviations
        assert_eq!(month_number("Jan").unwrap(), 1);
        assert_eq!(month_number("Feb").unwrap(), 2);
        assert_eq!(month_number("Mar").unwrap(), 3);
        assert_eq!(month_number("Apr").unwrap(), 4);
        assert_eq!(month_number("May").unwrap(), 5);
        assert_eq!(month_number("Jun").unwrap(), 6);
        assert_eq!(month_number("Jul").unwrap(), 7);
        assert_eq!(month_number("Aug").unwrap(), 8);
        assert_eq!(month_number("Sep").unwrap(), 9);
        assert_eq!(month_number("Oct").unwrap(), 10);
        assert_eq!(month_number("Nov").unwrap(), 11);
        assert_eq!(month_number("Dec").unwrap(), 12);

        // Test invalid month abbreviation
        let result = month_number("Invalid");
        assert!(result.is_err());
        assert!(result
            .unwrap_err()
            .to_string()
            .contains("does not match mappings"));
    }

    #[test]
    fn test_date_new() {
        // Test valid date
        let date = Date::new(2024, 3, 25).unwrap();
        assert_eq!(date.year(), 2024);
        assert_eq!(date.month(), 3);
        assert_eq!(date.day(), 25);

        // Test invalid date - February 30th
        let invalid_date = Date::new(2024, 2, 30);
        assert!(invalid_date.is_err());
        assert!(invalid_date
            .unwrap_err()
            .to_string()
            .contains("Invalid date"));
    }

    #[test]
    fn test_date_from_csv() {
        // Test valid CSV date
        let date = Date::from_csv("25/Mar/24").unwrap();
        assert_eq!(date.year(), 2024);
        assert_eq!(date.month(), 3);
        assert_eq!(date.day(), 25);

        // Test invalid format (wrong delimiter)
        let invalid_format = Date::from_csv("25-Mar-24");
        assert!(invalid_format.is_err());
        assert!(invalid_format
            .unwrap_err()
            .to_string()
            .contains("Invalid date format"));

        // Test invalid month
        let invalid_month = Date::from_csv("25/Xyz/24");
        assert!(invalid_month.is_err());
        assert!(invalid_month
            .unwrap_err()
            .to_string()
            .contains("does not match mappings"));

        // Test invalid day (non-numeric)
        let invalid_day = Date::from_csv("XX/Mar/24");
        assert!(invalid_day.is_err());
    }

    #[test]
    fn test_date_component_accessors() {
        let date = Date::new(2024, 3, 25).unwrap();

        // Test year accessor
        assert_eq!(date.year(), 2024);

        // Test month accessor
        assert_eq!(date.month(), 3);

        // Test day accessor
        assert_eq!(date.day(), 25);
    }

    #[test]
    fn test_financial_year_calculations() {
        // Test dates in the same financial year
        let date1 = Date::new(2023, 7, 1).unwrap(); // Start of FY 2023-2024
        let date2 = Date::new(2024, 6, 30).unwrap(); // End of FY 2023-2024

        assert_eq!(Date::which_fy(&date1), 2023);
        assert_eq!(Date::which_fy(&date2), 2023);
        assert!(!Date::in_different_fy(&date1, &date2));

        // Test dates in different financial years
        let date3 = Date::new(2024, 7, 1).unwrap(); // Start of FY 2024-2025

        assert_eq!(Date::which_fy(&date3), 2024);
        assert!(Date::in_different_fy(&date1, &date3));
        assert!(Date::in_different_fy(&date2, &date3));
    }

    #[test]
    fn test_format_fy() {
        assert_eq!(Date::format_fy(2023), "2023-2024");
        assert_eq!(Date::format_fy(2024), "2024-2025");
        assert_eq!(Date::format_fy(2000), "2000-2001");
    }

    #[test]
    fn test_cgt_discount_eligibility() {
        // Test exactly one year (not eligible)
        let buy_date = Date::new(2023, 3, 25).unwrap();
        let sell_date = Date::new(2024, 3, 24).unwrap();
        assert!(!Date::is_eligible_for_cgt_discount(&buy_date, &sell_date));

        // Test more than one year (eligible)
        let eligible_sell_date = Date::new(2024, 3, 25).unwrap();
        assert!(Date::is_eligible_for_cgt_discount(
            &buy_date,
            &eligible_sell_date
        ));

        // Test less than one year (not eligible)
        let ineligible_sell_date = Date::new(2023, 9, 25).unwrap();
        assert!(!Date::is_eligible_for_cgt_discount(
            &buy_date,
            &ineligible_sell_date
        ));
    }

    #[test]
    fn test_dummy_date() {
        let dummy = Date::dummy();
        assert_eq!(dummy.year(), 2000);
        assert_eq!(dummy.month(), 6);
        assert_eq!(dummy.day(), 1);
    }

    #[test]
    fn test_try_from_string() {
        // Test valid ISO date string
        let date_str = String::from("2024-03-25");
        let date = Date::try_from(date_str).unwrap();
        assert_eq!(date.year(), 2024);
        assert_eq!(date.month(), 3);
        assert_eq!(date.day(), 25);

        // Test invalid date format
        let invalid_str = String::from("25/03/2024");
        let result = Date::try_from(invalid_str);
        assert!(result.is_err());

        // Test invalid date value
        let invalid_date = String::from("2024-02-30");
        let result = Date::try_from(invalid_date);
        assert!(result.is_err());
    }

    #[test]
    fn test_display() {
        let date = Date::new(2024, 3, 25).unwrap();
        assert_eq!(date.to_string(), "2024-03-25");
    }

    #[test]
    fn test_sqlite_integration() -> SqliteResult<()> {
        // Create an in-memory SQLite database for testing
        let conn = Connection::open_in_memory()?;

        // Create a test table with a date column
        conn.execute(
            "CREATE TABLE test_dates (id INTEGER PRIMARY KEY, date_value TEXT)",
            [],
        )?;

        // Insert a date using the ToSql implementation
        let test_date = Date::new(2024, 3, 25).unwrap();
        conn.execute(
            "INSERT INTO test_dates (id, date_value) VALUES (1, ?)",
            [&test_date],
        )?;

        // Retrieve the date using the FromSql implementation
        let retrieved_date: Date = conn.query_row(
            "SELECT date_value FROM test_dates WHERE id = 1",
            [],
            |row| row.get(0),
        )?;

        // Verify the retrieved date matches the original
        assert_eq!(retrieved_date, test_date);
        assert_eq!(retrieved_date.year(), 2024);
        assert_eq!(retrieved_date.month(), 3);
        assert_eq!(retrieved_date.day(), 25);

        Ok(())
    }

    #[test]
    fn test_ordering() {
        let date1 = Date::new(2023, 1, 1).unwrap();
        let date2 = Date::new(2023, 1, 2).unwrap();
        let date3 = Date::new(2023, 2, 1).unwrap();
        let date4 = Date::new(2024, 1, 1).unwrap();

        // Test equality
        let date1_clone = Date::new(2023, 1, 1).unwrap();
        assert_eq!(date1, date1_clone);

        // Test ordering
        assert!(date1 < date2);
        assert!(date2 < date3);
        assert!(date3 < date4);
    }
}

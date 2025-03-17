use anyhow::{bail, Error, Result};

pub fn month(val: &str) -> Result<u32> {
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

#[derive(Debug, Clone)]
pub struct Date {
    pub day: u32,
    pub month: u32,
    pub year: u32,
}

impl TryFrom<String> for Date {
    fn try_from(str_date: String) -> std::result::Result<Self, Self::Error> {
        let arr: Vec<&str> = str_date.split("-").collect();
        Ok(Date {
            day: arr[0].parse()?,
            month: arr[1].parse()?,
            year: arr[2].parse()?,
        })
    }
    type Error = Error;
}

impl Date {
    pub fn from_csv(date: String) -> Result<Date> {
        let arr: Vec<&str> = date.split("/").collect();
        let date = format!("{}-{}-{}", arr[0], month(arr[1])?, arr[2]);
        Ok(date.try_into()?)
    }

    pub fn in_same_fy(old_date: &Date, new_date: &Date) -> bool {
        let old_fy = Self::which_fy(old_date);
        let new_fy = Self::which_fy(new_date);
        old_fy != new_fy // Fixed logic - returns true if they're in different FYs
    }

    /// Returns the financial year that a particular date is set in
    /// This is the year that FY STARTED in
    /// i.e. july 1 2024 -> 2024
    /// jan 15 2024 -> 2023 (July 1, 2023 - June 30, 2024)
    pub fn which_fy(date: &Date) -> u32 {
        match date.month {
            7..=12 => date.year,
            1..=6 => date.year - 1,
            _ => panic!(),
        }
    }
}
/// Convert from CSV format into date

impl std::fmt::Display for Date {
    // This trait requires `fmt` with this exact signature.
    fn fmt(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result {
        // In the database, we're storing dates in DD-MM-YY format
        write!(f, "{:0>2}-{:0>2}-{:0>2}", self.day, self.month, self.year)
    }
}

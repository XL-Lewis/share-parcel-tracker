use chrono::prelude::*;

pub fn date_string_to_unix_i64(date_str: &str) -> Result<i64, chrono::ParseError> {
    let parsed_date = NaiveDate::parse_from_str(date_str, "%d/%b/%y")?;
    let datetime = parsed_date.and_hms_opt(0, 0, 0).expect("Invalid time");
    let datetime_utc = DateTime::<Utc>::from_naive_utc_and_offset(datetime, Utc);
    Ok(datetime_utc.timestamp())
}

pub fn date_unix_i64_into_string(date: i64) -> String {
    let datetime = Utc.timestamp_opt(date, 0).unwrap();
    return datetime.format("%Y-%m-%d").to_string();
}

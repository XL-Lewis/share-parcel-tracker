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
        let arr: Vec<&str> = str_date.split("/").collect();
        Ok(Date {
            day: arr[0].parse()?,
            month: arr[1].parse()?,
            year: arr[2].parse()?,
        })
    }
    type Error = Error;
}

pub fn initial_convert(date: String) -> Result<Date> {
    let arr: Vec<&str> = date.split("/").collect();
    let date = format!("{}/{}/{}", arr[0], month(arr[1])?, arr[2]);
    Ok(date.try_into()?)
}

impl std::fmt::Display for Date {
    // This trait requires `fmt` with this exact signature.
    fn fmt(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result {
        // Write strictly the first element into the supplied output
        // stream: `f`. Returns `fmt::Result` which indicates whether the
        // operation succeeded or failed. Note that `write!` uses syntax which
        // is very similar to `println!`.
        write!(f, "{:0>2}/{:0>2}/{:0>2}", self.year, self.month, self.day)
    }
}

pub fn next_fy(old_date: &Date, new_date: &Date) -> bool {
    let old_fy = which_fy(old_date);
    let new_fy = which_fy(new_date);
    !old_fy == new_fy
}

fn which_fy(date: &Date) -> u32 {
    match date.month {
        7..=12 => date.year,
        1..=6 => date.year - 1,
        _ => panic!(),
    }
}

# Share Parcel Tracker

A basic Rust application demonstrating SQLite integration using the `rusqlite` crate.

## Features

- SQLite database connection and operation
- Table creation
- Data insertion
- Basic querying with parameters
- Structured Rust types mapped to database records

## Getting Started

### Prerequisites

- Rust and Cargo (latest stable version recommended)

### Running the Project

```bash
cargo run
```

This will:
1. Create an SQLite database file named `parcels.db` if it doesn't exist
2. Create a `parcels` table if it doesn't exist
3. Insert sample parcel data
4. Query and display all parcels
5. Query and display parcels being sent to Sydney

## Project Structure

- `src/main.rs`: Contains all the code for the application
- `parcels.db`: SQLite database file (created when you run the application)

## SQLite Operations Demonstrated

1. **Connecting to a database**:
   ```rust
   let conn = Connection::open("parcels.db")?;
   ```

2. **Creating tables**:
   ```rust
   conn.execute(
       "CREATE TABLE IF NOT EXISTS parcels (
           id INTEGER PRIMARY KEY,
           tracking_number TEXT NOT NULL,
           ...
       )",
       [],
   )?;
   ```

3. **Inserting data**:
   ```rust
   conn.execute(
       "INSERT OR REPLACE INTO parcels VALUES (?1, ?2, ?3, ?4, ?5)",
       params![parcel.id, parcel.tracking_number, /* ... */],
   )?;
   ```

4. **Querying data**:
   ```rust
   let mut stmt = conn.prepare("SELECT * FROM parcels")?;
   let results = stmt.query_map([], |row| { /* ... */ })?;
   ```

5. **Parameterized queries**:
   ```rust
   stmt.query_map(["Sydney"], |row| { /* ... */ })?;
   ```

## Next Steps

Here are some ways you could extend this project:

1. **Add more complex queries** - Try using SQL aggregation, JOINs, or subqueries
2. **Implement a connection pool** - Add `r2d2` and `r2d2_sqlite` to manage database connections efficiently
3. **Create a CLI interface** - Add `clap` for command line arguments to perform different operations
4. **Add migrations** - Implement a schema migration system for database changes
5. **Implement a REST API** - Add `actix-web` or `rocket` to expose your data via HTTP
6. **Add transactions** - Use SQLite transactions for atomic operations
7. **Implement a repository pattern** - Create separate modules for database operations

## Resources

- [rusqlite documentation](https://docs.rs/rusqlite/latest/rusqlite/)
- [SQLite documentation](https://www.sqlite.org/docs.html)


# TODO:

- [ ] Hook up database
- [ ] Link sell to buy transactions
- [ ] Testing
- [ ] Summarize current state of stock
- [ ] Summarize all outstanding stocks
- [ ] UI to allow viewing of stocks
- [ ] UI tool to select buy for associated sell
- [ ] UI to manually set fields for a transaction



# share-parcel-tracker
A tracking program to help manage shares

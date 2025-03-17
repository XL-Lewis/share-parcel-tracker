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

- [X] Hook up database
- [X] Summarize current state of stock
- [X] Summarize all outstanding stocks
- [ ] Link sell to buy transactions
- [ ] Testing
- [ ] Clean up date and readme
- [ ] UI to allow viewing of stocks
- [ ] UI tool to select buy for associated sell
- [ ] UI to manually set fields for a transaction
- [ ] Fifo auto


# share-parcel-tracker
A tracking program to help manage shares

// @generated automatically by Diesel CLI.

diesel::table! {
    transactions (id) {
        id -> Text,
        ticker -> Text,
        num_sold -> Integer,
        price -> Float,
        date -> Integer,
        description -> Nullable<Text>,
    }
}

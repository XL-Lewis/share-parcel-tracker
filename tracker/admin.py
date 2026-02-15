from django.contrib import admin

from .models import Security, ImportRecord, Transaction, Parcel, ParcelMatch


class TransactionInline(admin.TabularInline):
    model = Transaction
    extra = 0
    fields = [
        "trade_date",
        "transaction_type",
        "quantity",
        "unit_price",
        "brokerage",
        "total_value",
    ]
    readonly_fields = fields
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False


class ParcelMatchInline(admin.TabularInline):
    model = ParcelMatch
    extra = 0
    fields = [
        "parcel",
        "matched_quantity",
        "cost_base_aud",
        "proceeds_aud",
        "capital_gain_loss",
        "holding_period_days",
        "cgt_discount_eligible",
        "discount_amount",
        "net_capital_gain",
    ]
    readonly_fields = fields
    show_change_link = True
    fk_name = "sell_transaction"

    def has_add_permission(self, request, obj=None):
        return False


class ParcelMatchByParcelInline(admin.TabularInline):
    model = ParcelMatch
    extra = 0
    fields = [
        "sell_transaction",
        "matched_quantity",
        "cost_base_aud",
        "proceeds_aud",
        "capital_gain_loss",
        "net_capital_gain",
    ]
    readonly_fields = fields
    show_change_link = True
    fk_name = "parcel"
    verbose_name = "match"
    verbose_name_plural = "matches"

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Security)
class SecurityAdmin(admin.ModelAdmin):
    list_display = ["ticker", "name", "exchange", "currency", "asset_type"]
    list_filter = ["exchange", "currency", "asset_type"]
    search_fields = ["ticker", "name"]


@admin.register(ImportRecord)
class ImportRecordAdmin(admin.ModelAdmin):
    list_display = ["filename", "source_type", "row_count", "imported_at"]
    list_filter = ["source_type"]
    readonly_fields = ["imported_at"]


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = [
        "trade_date",
        "security",
        "transaction_type",
        "quantity",
        "unit_price",
        "brokerage",
        "total_value",
        "currency",
    ]
    list_filter = ["transaction_type", "security", "currency"]
    search_fields = ["security__ticker"]
    date_hierarchy = "trade_date"
    inlines = [ParcelMatchInline]


@admin.register(Parcel)
class ParcelAdmin(admin.ModelAdmin):
    list_display = [
        "security",
        "acquisition_date",
        "original_quantity",
        "remaining_quantity",
        "cost_per_unit_aud",
        "total_cost_base_aud",
        "is_fully_matched",
    ]
    list_filter = ["is_fully_matched", "security"]
    search_fields = ["security__ticker"]
    date_hierarchy = "acquisition_date"
    inlines = [ParcelMatchByParcelInline]


@admin.register(ParcelMatch)
class ParcelMatchAdmin(admin.ModelAdmin):
    list_display = [
        "parcel",
        "sell_transaction",
        "matched_quantity",
        "cost_base_aud",
        "proceeds_aud",
        "capital_gain_loss",
        "cgt_discount_eligible",
        "discount_amount",
        "net_capital_gain",
    ]
    list_filter = ["cgt_discount_eligible"]
    search_fields = ["parcel__security__ticker"]

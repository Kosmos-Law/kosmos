from django.urls import path

from apps.accounting import views

app_name = "accounting"

urlpatterns = [
    path("accounting/", views.accounting_index, name="index"),
    path("accounting/sync/", views.accounting_sync, name="sync"),
    # Chart of accounts
    path("accounting/accounts/", views.accounts_index, name="accounts-index"),
    path("accounting/accounts/list/", views.accounts_list, name="accounts-list"),
    path("accounting/accounts/add/", views.account_add, name="account-add"),
    path("accounting/accounts/seed/", views.accounts_seed, name="accounts-seed"),
    path("accounting/accounts/tree/toggle/", views.tree_toggle, name="tree-toggle"),
    path("accounting/accounts/tree/<str:state>/", views.tree_fold, name="tree-fold"),
    path(
        "accounting/accounts/tree-inactive/",
        views.tree_show_inactive,
        name="tree-inactive",
    ),
    path("accounting/accounts/<int:pk>/edit/", views.account_edit, name="account-edit"),
    path("accounting/accounts/<int:pk>/", views.account_ledger, name="account-ledger"),
    # Journal
    path("accounting/journal/", views.journal_index, name="journal-index"),
    path("accounting/journal/list/", views.journal_list, name="journal-list"),
    path("accounting/journal/add/", views.entry_add, name="entry-add"),
    path("accounting/journal/<int:pk>/", views.entry_detail, name="entry-detail"),
    path("accounting/journal/<int:pk>/edit/", views.entry_edit, name="entry-edit"),
    path(
        "accounting/journal/<int:pk>/delete/", views.entry_delete, name="entry-delete"
    ),
    path(
        "accounting/journal/<int:pk>/reverse/",
        views.entry_reverse,
        name="entry-reverse",
    ),
    # Statements
    path("accounting/statements/", views.statements_index, name="statements-index"),
    path(
        "accounting/statements/trial-balance/",
        views.trial_balance_view,
        name="trial-balance",
    ),
    path(
        "accounting/statements/profit-and-loss/",
        views.profit_and_loss_view,
        name="profit-and-loss",
    ),
    path(
        "accounting/statements/balance-sheet/",
        views.balance_sheet_view,
        name="balance-sheet",
    ),
    path(
        "accounting/statements/tax-summary/", views.tax_summary_view, name="tax-summary"
    ),
]

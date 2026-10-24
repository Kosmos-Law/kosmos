from django.urls import path

from apps.books import views

app_name = "books"

urlpatterns = [
    path("books/", views.books_index, name="index"),
    path("books/sync/", views.books_sync, name="sync"),
    # Chart of accounts
    path("books/accounts/", views.accounts_index, name="accounts-index"),
    path("books/accounts/list/", views.accounts_list, name="accounts-list"),
    path("books/accounts/add/", views.account_add, name="account-add"),
    path("books/accounts/seed/", views.accounts_seed, name="accounts-seed"),
    path("books/accounts/tree/toggle/", views.tree_toggle, name="tree-toggle"),
    path("books/accounts/tree/<str:state>/", views.tree_fold, name="tree-fold"),
    path(
        "books/accounts/tree-inactive/",
        views.tree_show_inactive,
        name="tree-inactive",
    ),
    path("books/accounts/<int:pk>/edit/", views.account_edit, name="account-edit"),
    path("books/accounts/<int:pk>/", views.account_ledger, name="account-ledger"),
    # Journal
    path("books/journal/", views.journal_index, name="journal-index"),
    path("books/journal/list/", views.journal_list, name="journal-list"),
    path("books/journal/add/", views.entry_add, name="entry-add"),
    path("books/journal/<int:pk>/", views.entry_detail, name="entry-detail"),
    path("books/journal/<int:pk>/edit/", views.entry_edit, name="entry-edit"),
    path("books/journal/<int:pk>/delete/", views.entry_delete, name="entry-delete"),
    path("books/journal/<int:pk>/reverse/", views.entry_reverse, name="entry-reverse"),
    # Statements
    path("books/statements/", views.statements_index, name="statements-index"),
    path(
        "books/statements/trial-balance/",
        views.trial_balance_view,
        name="trial-balance",
    ),
    path(
        "books/statements/profit-and-loss/",
        views.profit_and_loss_view,
        name="profit-and-loss",
    ),
    path(
        "books/statements/balance-sheet/",
        views.balance_sheet_view,
        name="balance-sheet",
    ),
    path("books/statements/tax-summary/", views.tax_summary_view, name="tax-summary"),
]

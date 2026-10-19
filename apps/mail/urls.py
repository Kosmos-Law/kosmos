"""The Emails tab of the case shell and its email operations. The paths keep
their /case/ prefix (the tab lives there); the names moved to the ``mail``
namespace when the routes left the case app.
"""

from django.urls import path

from apps.mail import views

app_name = "mail"

urlpatterns = [
    path("case/<int:matter_id>/emails/", views.emails_index, name="emails-index"),
    path("case/<int:matter_id>/emails/list/", views.emails_list, name="emails-list"),
    path(
        "case/<int:matter_id>/emails/list/items/",
        views.emails_list_items,
        name="emails-list-items",
    ),
    path(
        "case/<int:matter_id>/emails/label/link/",
        views.label_link_modal,
        name="emails-label-link-modal",
    ),
    path(
        "case/<int:matter_id>/emails/label/link/set/",
        views.label_link,
        name="emails-label-link",
    ),
    path(
        "case/<int:matter_id>/emails/label/unlink/",
        views.label_unlink,
        name="emails-label-unlink",
    ),
    path(
        "case/<int:matter_id>/emails/refresh/",
        views.emails_refresh,
        name="emails-refresh",
    ),
    path(
        "case/<int:matter_id>/emails/refresh/status/",
        views.emails_refresh_status,
        name="emails-refresh-status",
    ),
    path(
        "case/<int:matter_id>/emails/filter/",
        views.emails_filter,
        name="emails-filter",
    ),
    path(
        "case/<int:matter_id>/emails/filter/keyword/",
        views.emails_filter_keyword,
        name="emails-filter-keyword",
    ),
    path(
        "case/<int:matter_id>/emails/sort/<str:order>/",
        views.emails_sort,
        name="emails-sort",
    ),
    path(
        "case/emails/<int:email_id>/importance/<int:value>/",
        views.email_importance,
        name="email-importance",
    ),
    path(
        "case/emails/<int:email_id>/preview/",
        views.email_preview,
        name="email-preview",
    ),
    path(
        "case/emails/<int:email_id>/promote/",
        views.email_promote,
        name="email-promote",
    ),
]

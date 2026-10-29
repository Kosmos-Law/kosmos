from django.urls import path

from . import views

app_name = "drive"

urlpatterns = [
    path(
        "case/<int:matter_id>/folder/modal/",
        views.folder_link_modal,
        name="folder-link-modal",
    ),
    path("case/<int:matter_id>/folder/link/", views.folder_link, name="folder-link"),
    path(
        "case/<int:matter_id>/folder/unlink/",
        views.folder_unlink,
        name="folder-unlink",
    ),
    path("settings/files/", views.files_status, name="files-status"),
]

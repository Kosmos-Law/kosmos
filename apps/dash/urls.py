from django.urls import path

from apps.dash.views import (
    dash_index,
    events_section,
    set_wip_period,
    week_tasks,
    wip_section,
)

app_name = "dash"

urlpatterns = [
    path("dash/", dash_index, name="index"),
    path("dash/events/", events_section, name="events-section"),
    path("dash/events/tasks/<str:state>/", week_tasks, name="week-tasks"),
    path("dash/wip/", wip_section, name="wip-section"),
    path("dash/wip/period/<str:period>/", set_wip_period, name="wip-period"),
]

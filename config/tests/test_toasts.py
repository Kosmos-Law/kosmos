import json

from django.http import HttpResponse

from utils.toasts import add_toast, toast_error, toast_success


def test_first_toast_rides_in_hx_toast():
    response = toast_success(HttpResponse(), "Saved")

    assert json.loads(response["HX-Toast"]) == {
        "type": "success",
        "message": "Saved",
        "duration": 5000,
    }
    assert "HX-Toasts" not in response


def test_further_toasts_stack_without_replacing_the_first():
    response = HttpResponse()
    toast_success(response, "First")
    add_toast(response, "info", "Second")
    toast_error(response, "Third")

    assert json.loads(response["HX-Toast"])["message"] == "First"
    stacked = json.loads(response["HX-Toasts"])
    assert [t["message"] for t in stacked] == ["Second", "Third"]
    assert stacked[1]["type"] == "error"

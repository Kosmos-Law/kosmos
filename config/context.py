import os


def env(request):
    return {
        "env": os.environ.get("ENV"),
    }

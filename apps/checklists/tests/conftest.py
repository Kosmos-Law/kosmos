import pytest
from django.test import Client

from apps.accounts.models import CustomUser
from apps.checklists.models import ChecklistTemplate, ChecklistTemplateItem
from apps.matters.models import Matter, PracticeArea
from apps.tasks.models import Task


@pytest.fixture
def user():
    user = CustomUser.objects.create(
        username="Ollie", email="testuser@example.com", user_rate=100
    )
    user.set_password("clawboy")
    user.save()
    return user


@pytest.fixture
def client(user):
    client = Client()
    client.force_login(user)
    client.get("/dash/")  # Set daily dash session to avoid redirect
    return client


@pytest.fixture
def practice_area():
    return PracticeArea.objects.create(name="General", is_active=True)


@pytest.fixture
def matter(user, practice_area):
    return Matter.objects.create(
        user=user, name="Sample Test Matter", status="Open", practice_area=practice_area
    )


@pytest.fixture
def other_matter(practice_area):
    """An open matter nobody is assigned to."""
    return Matter.objects.create(
        name="Unassigned Matter", status="Open", practice_area=practice_area
    )


@pytest.fixture
def restricted(matter):
    """A user limited to assigned matters, assigned only ``matter``."""
    user = CustomUser.objects.create(
        username="Rae",
        email="rae@example.com",
        user_rate=150,
        perm_all_matters=False,
    )
    user.set_password("clawboy")
    user.save()
    matter.members.add(user)
    return user


@pytest.fixture
def restricted_client(restricted):
    client = Client()
    client.force_login(restricted)
    client.get("/dash/")
    return client


@pytest.fixture
def task(user, matter):
    return Task.objects.create(
        user=user, matter=matter, description="File the brief", status="Pending"
    )


@pytest.fixture
def other_task(user, other_matter):
    return Task.objects.create(
        user=user, matter=other_matter, description="Their filing", status="Pending"
    )


@pytest.fixture
def template():
    template = ChecklistTemplate.objects.create(name="Filing steps")
    ChecklistTemplateItem.objects.create(
        template=template, description="Proofread", order=1
    )
    ChecklistTemplateItem.objects.create(
        template=template, description="Serve", order=2
    )
    return template


@pytest.fixture
def second_template():
    template = ChecklistTemplate.objects.create(name="Closing steps")
    ChecklistTemplateItem.objects.create(
        template=template, description="Return the file", order=1
    )
    return template

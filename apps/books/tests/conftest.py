import pytest
from django.test import Client

from apps.accounts.models import CustomUser
from apps.books.chart import seed_default_chart
from apps.books.models import Account
from apps.settings.models import Firm


@pytest.fixture
def firm(db):
    """A firm with Books switched on."""
    firm = Firm.objects.first() or Firm.objects.create(name="Firm")
    firm.books_enabled = True
    firm.save()
    return firm


@pytest.fixture
def chart(firm):
    seed_default_chart()
    return {account.role: account for account in Account.objects.exclude(role="")}


def _client_for(user):
    client = Client()
    client.force_login(user)
    client.get("/dash/")  # Set daily dash session to avoid redirect
    return client


@pytest.fixture
def admin_client(firm):
    admin = CustomUser.objects.create(
        username="boss", email="boss@example.com", role="ADMIN"
    )
    admin.set_password("pw")
    admin.save()
    return _client_for(admin)


@pytest.fixture
def books_user(firm):
    user = CustomUser.objects.create(
        username="keeper", email="keeper@example.com", perm_books=True
    )
    user.set_password("pw")
    user.save()
    return user


@pytest.fixture
def books_client(books_user):
    return _client_for(books_user)


@pytest.fixture
def staff_client(firm):
    """A user without the Books permission."""
    user = CustomUser.objects.create(username="staff", email="staff@example.com")
    user.set_password("pw")
    user.save()
    return _client_for(user)

import pytest
from django.test import Client

from apps.accounting.chart import seed_default_chart
from apps.accounting.models import Account
from apps.accounts.models import CustomUser
from apps.settings.models import Firm


@pytest.fixture
def firm(db):
    """A firm with Accounting switched on."""
    firm = Firm.objects.first() or Firm.objects.create(name="Firm")
    firm.accounting_enabled = True
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
def accounting_user(firm):
    user = CustomUser.objects.create(
        username="keeper", email="keeper@example.com", perm_accounting=True
    )
    user.set_password("pw")
    user.save()
    return user


@pytest.fixture
def accounting_client(accounting_user):
    return _client_for(accounting_user)


@pytest.fixture
def staff_client(firm):
    """A user without the Accounting permission."""
    user = CustomUser.objects.create(username="staff", email="staff@example.com")
    user.set_password("pw")
    user.save()
    return _client_for(user)

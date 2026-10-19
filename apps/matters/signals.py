"""Signals the matter app sends, for the apps that keep state alongside a
matter without the matter app knowing them (the Drive mirror drops its
folder mappings when a matter closes)."""

from django.dispatch import Signal

# Sent from Matter.save() as a matter goes from an open status to a closed
# one, before the row is written. Arguments: ``matter``.
matter_closed = Signal()

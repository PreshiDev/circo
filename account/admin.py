from django.contrib import admin
from .models import User, Contact, Event, Interaction

admin.site.register(User)
admin.site.register(Contact)
admin.site.register(Event)
admin.site.register(Interaction)
from django.contrib import admin

from .models import Trip


@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = ("id", "pickup_location", "dropoff_location",
                    "current_cycle_used", "created_at")
    search_fields = ("current_location", "pickup_location", "dropoff_location")

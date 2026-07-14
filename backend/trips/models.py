from django.db import models


class Trip(models.Model):
    """A planned trip. Stores the inputs and the computed plan for later recall."""
    current_location = models.CharField(max_length=255)
    pickup_location = models.CharField(max_length=255)
    dropoff_location = models.CharField(max_length=255)
    current_cycle_used = models.FloatField(help_text="Hours already used in the 70h/8day cycle.")

    plan = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.pickup_location} → {self.dropoff_location} ({self.created_at:%Y-%m-%d})"

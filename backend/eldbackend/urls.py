from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def root(request):
    return JsonResponse({
        "service": "ELD Trip Planner API",
        "endpoints": ["/api/health/", "/api/plan/", "/api/trips/"],
    })


urlpatterns = [
    path("", root),
    path("admin/", admin.site.urls),
    path("api/", include("trips.urls")),
]

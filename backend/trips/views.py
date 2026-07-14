from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import Trip
from .serializers import TripInputSerializer, TripSerializer
from .services import routing
from .services.planner import plan_trip


@api_view(["GET"])
def health(request):
    return Response({"status": "ok"})


@api_view(["POST"])
def plan(request):
    """Plan a trip: validate inputs, run the HOS planner, persist and return it."""
    serializer = TripInputSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    try:
        result = plan_trip(
            current_location=data["current_location"],
            pickup_location=data["pickup_location"],
            dropoff_location=data["dropoff_location"],
            current_cycle_used=data["current_cycle_used"],
        )
    except routing.RoutingError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    trip = Trip.objects.create(
        current_location=data["current_location"],
        pickup_location=data["pickup_location"],
        dropoff_location=data["dropoff_location"],
        current_cycle_used=data["current_cycle_used"],
        plan=result,
    )
    result["trip_id"] = trip.id
    return Response(result, status=status.HTTP_200_OK)


@api_view(["GET"])
def trip_detail(request, pk):
    try:
        trip = Trip.objects.get(pk=pk)
    except Trip.DoesNotExist:
        return Response({"error": "Trip not found."}, status=status.HTTP_404_NOT_FOUND)
    return Response(TripSerializer(trip).data)


@api_view(["GET"])
def trip_list(request):
    trips = Trip.objects.all()[:25]
    return Response(TripSerializer(trips, many=True).data)

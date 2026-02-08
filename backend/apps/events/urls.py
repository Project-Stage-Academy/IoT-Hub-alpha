from django.urls import path

from .views import EventAcknowledgeView, EventDetailView, EventListView, EventResolveView

urlpatterns = [
    path("", EventListView.as_view(), name="event_list"),
    path("<int:event_id>/", EventDetailView.as_view(), name="event_detail"),
    path("<int:event_id>/ack/", EventAcknowledgeView.as_view(), name="event_ack"),
    path("<int:event_id>/resolve/", EventResolveView.as_view(), name="event_resolve"),
]

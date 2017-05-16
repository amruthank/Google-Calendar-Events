from django.conf.urls import patterns, url

from Polls import views

urlpatterns = patterns('',

        # example: /createCalenderEvent
        url(r'^createCalenderEvent/$', views.createCalenderEvent, name='createCalenderEvent'),
        # example: /editCalendarEvent
        url(r'^editCalendarEvent/(?P<event_id>\S+)/$', views.editCalendarEvent, name='editCalendarEvent'),
        # example: /deleteCalendarEvent
        url(r'^deleteCalendarEvent/(?P<event_id>\S+)/$', views.deleteCalendarEvent, name='deleteCalendarEvent'),
        # example: /showMyEvents
        url(r'^showMyEvents/$', views.showMyEvents, name='showMyEvents'),
)


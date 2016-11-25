from django.shortcuts import render, render_to_response

from django.core import serializers

from django.http import HttpResponse, HttpResponseRedirect
from django.db.models.base import ObjectDoesNotExist
from django.contrib.auth.models import User
from polls.models import *

from apiclient import discovery
from oauth2client import client
from oauth2client import tools
from oauth2client.file import Storage
import httplib2


# Parser for the google calender Handler XML
class CalenderHandler(xml.sax.ContentHandler):
	def __init__(self):
		self.node = ''
		self.params = {}
		self.participants = {}
		self.is_participant = False;
		self.num = 0
		self.email = ''

	def startElement(self, name, attrs):
		self.node = name
		if name == "participant":
			self.is_participant = True

	def endElement(self, name):
		if name == "participant":
			self.participants[self.num] = self.email
			self.num += 1
			self.is_participant = False
			self.email = None

		if name == "participants":
			self.params["participants"] = self.participants
			
		self.node = ''	

	def characters(self,content):
		if self.node:
			if self.is_participant:
				if self.node == "participant":
					self.email = _my_unescape(content)
			else:
				if self.params.has_key(self.node.lower()):
					self.params[self.node.lower()] += _my_unescape(content)
				else:
					self.params[self.node.lower()] = _my_unescape(content)
#End of CalenderHandler()




#Helper function to return the Google Credential
def _get_google_credential():
	SCOPES = ['https://www.googleapis.com/auth/calendar','https://www.googleapis.com/auth/calendar.readonly', 'https://www.googleapis.com/auth/plus.login']
	CLIENT_SECRET_FILE = 'credentials.json'  #Google Credential PATH
	APPLICATION_NAME = 'Google Calendar API Python Quickstart'
	
	try:
		import argparse
		flags = argparse.ArgumentParser(parents=[tools.argparser]).parse_args()
	except ImportError:
		flags = None
	
	store = Storage(CLIENT_SECRET_FILE) 
	credentials = store.get()

	if credentials is None:
		flow = client.flow_from_clientsecrets(CLIENT_SECRET_FILE, SCOPES)
		credentials = tools.run_flow(flow, store, flags) 

	http = credentials.authorize(httplib2.Http())
	service = discovery.build('calendar', 'v3', http=http)
	return service
#End of _get_google_credential()



#POST /^createCalenderEvent
def createCalenderEvent(request):
	logr.info("Incoming request to create a google calender event by User %s"%request.user.email)
	
	if request.method != 'POST':
		return HttpResponse(INVALID_METHOD, content_type="text/xml")

	# Read the request body
        xmlData = urllib.unquote_plus(request.body)

        if xmlData.startswith('data='):
                xmlData = xmlData[5:]

	calHandler = CalenderHandler() 
	xml.sax.parseString(xmlData,calHandler)

	EVENT = {}	#Calendar Event Dictionary
	GMT_OFF = '+05:30'      # PDT/MST/GMT-7

	if not calHandler.params.has_key("interviewtype"):
		return HttpResponse(EMPTY_FIELD_ERR % "Missing Calendar Type", content_type="text/xml")
	else:
		EVENT['summary'] = calHandler.params["interviewtype"]

	if (not calHandler.params.has_key("startdate")) or (not calHandler.params.has_key("starttime")):
		return HttpResponse(EMPTY_FIELD_ERR % "Missing Start Date/time", content_type="text/xml")
	else:
		start_date = '%sT%s%s'%(calHandler.params["startdate"],calHandler.params["starttime"],GMT_OFF)
		EVENT['start'] ={}
		EVENT['start']['dateTime'] = start_date 

	if (not calHandler.params.has_key("endate")) and (not calHandler.params.has_key("endtime")):
		return HttpResponse(EMPTY_FIELD_ERR % "Missing End Date/Time", content_type="text/xml")
	else:
		end_date = '%sT%s%s'%(calHandler.params["enddate"],calHandler.params["endtime"],GMT_OFF)
		EVENT['end'] ={}
		EVENT['end']['dateTime'] = end_date 

	if not calHandler.params.has_key("description"):
		return HttpResponse(EMPTY_FIELD_ERR % "Missing Description", content_type="text/xml")
	else:
		EVENT['description'] = calHandler.params["description"]

	if not calHandler.params.has_key("participants"):
		return HttpResponse(EMPTY_FIELD_ERR % "Missing participants", content_type="text/xml")
	else:	
		attendees = {}
		for participant in calHandler.params["participants"]:
			attendees[participant] = {}
			attendees[participant]["email"] = calHandler.params["participants"][participant]

		data = []
		for key, value in attendees.iteritems():
		    	data.append(value)

		EVENT['attendees'] = data

	if calHandler.params.has_key("location"):
		EVENT['location'] = calHandler.params["location"]

	service = _get_google_credential() #Helper function to get the google credential
	event = service.events().insert(calendarId='primary',sendNotifications=True, body=EVENT).execute() #New Event
	logr.info("EVENT = %s"%event)
	
	if event:
		#Create meeting object
		meeting = Meeting()
		meeting.event_id = event["id"]
		meeting.start_time = event["start"]["dateTime"]
		meeting.end_time = event["end"]["dateTime"]
		meeting.description = event["description"]
		if calHandler.params.has_key("location"):
			meeting.location = event["location"]
		meeting.interview_type = event["summary"]
		meeting.schedule_count += 1 
		meeting.create_time = datetime.now()
		meeting.save()
	else:
		return HttpResponse(INVALID_METHOD, content_type="text/xml")
	
	for guest in calHandler.params["participants"].values():
		participant = Participant()	#Creating participant object
		participant.meeting = Meeting.objects.get(event_id = event["id"])
		try:
			user = User.objects.get(email= guest)
		except User.DoesNotExist:
			user = User.objects.create_user(username=guest,email=guest)
			user.save()
		participant.user = user
		participant.role = participant_type
		participant.save()

	resp = '<?xml version="1.0" encoding="UTF-8"?>\r\n'
	resp += '<response>\r\n'
	resp += _add_xml_field("EventId", event["id"] ,1)
	resp += '\t<success>%s</success>\r\n' % ("Successfully created calendar event")
	resp += '</response>\r\n'
	return HttpResponse(resp, content_type="text/xml")	
#End of createCalenderEvent()




#POST /^editCalendarEvent/<event_id>/
def editCalendarEvent(request,event_id):
	logr.info("Incoming request to update the Calendar Event by %s"%request.user.email)
	
	try:
		meeting = Meeting.objects.get(event_id = event_id)
	except Exception:
		return HttpResponse(BAD_REQUEST % "Event ID", content_type="text/xml")
	
	# Read the request body
        xmlData = urllib.unquote_plus(request.body)

        if xmlData.startswith('data='):
                xmlData = xmlData[5:]

	calHandler = CalenderHandler() 
	xml.sax.parseString(xmlData,calHandler)

	service = _get_google_credential() 		#Helper function to get the google credential
	event = service.events().get(calendarId='primary', eventId=event_id).execute() 		#Get the Event
	
	if event:
		GMT_OFF = '+05:30'      # PDT/MST/GMT-7
		if calHandler.params.has_key("startdate") or calHandler.params.has_key("starttime"):
			start_date = '%sT%s%s'%(calHandler.params["startdate"],calHandler.params["starttime"],GMT_OFF)
			event['start']['dateTime'] = start_date
			meeting.start_time = event['start']['dateTime']
		if calHandler.params.has_key("enddate") or calHandler.params.has_key("endtime"):
			end_date = '%sT%s%s'%(calHandler.params["enddate"],calHandler.params["endtime"],GMT_OFF)
			event['end']['dateTime'] = end_date
			meeting.end_time = event['end']['dateTime']	
			logr.info("END DATE = %s"%end_date)
		if calHandler.params.has_key("description"):
			event['description'] = calHandler.params["description"]
			meeting.description = calHandler.params["description"]
		if calHandler.params.has_key("location"):
			event['location'] = calHandler.params["location"]
			meeting.location = calHandler.params["location"]
		if calHandler.params.has_key("interviewtype"):
			event['summary'] = calHandler.params["interviewtype"]
			meeting.interview_type = calHandler.params["interviewtype"]
		if calHandler.params.has_key("participants"):
			for key,values in calHandler.params["participants"].iteritems():
				participants = Participant.objects.filter(meeting_id = meeting.id).filter(user__email = values)
				if len(participants)==0:
					participant = Participant()	#Creating participant object
					participant.meeting = Meeting.objects.get(event_id = event["id"])
					try:
						user = User.objects.get(email= values)
					except User.DoesNotExist:
						user = User.objects.create_user(username=values,email=values)
						user.save()
					participant.user = user
					participant.save()
				else:
					continue
	else:
		return HttpResponse(BAD_REQUEST % "Event ID", content_type="text/xml")

	meeting.schedule_count += 1
	meeting.save()
	
	updated_event = service.events().update(calendarId='primary', eventId=event['id'], body=event).execute() #Update Event

	resp = '<?xml version="1.0" encoding="UTF-8"?>\r\n'
	resp += '<CalendarEvent>\r\n'
	resp += _add_xml_field("status", event['status'],1)
	resp += _add_xml_field("InterviewType", event['summary'],1)
	resp += _add_xml_field("Description", event['description'],1)
	resp += _add_xml_field("StartDate", event['start']['dateTime'],1)
	resp += _add_xml_field("EndDate", event['end']['dateTime'],1)
	resp += _add_xml_field("location", event['location'],1)

	resp += '\t<Attendees>\r\n'
	for key in event['attendees']:
		resp += _add_xml_field("attendee", key["email"],2)
	resp += '\t</Attendees>\r\n'

	resp += '</CalendarEvent>\r\n'
	return HttpResponse(resp, content_type="text/xml")		
#End of editCalendarEvent()




#POST /^deleteCalendarEvent/
def deleteCalendarEvent(request,event_id):
	logr.info("Incoming request to delete the Calendar Event by %s"%request.user.email)

	try:
		meeting = Meeting.objects.get(event_id = event_id)
	except Exception:
		return HttpResponse(BAD_REQUEST % "Event ID", content_type="text/xml")

	service = _get_google_credential()
	service.events().delete(calendarId='primary', eventId=event_id).execute()
	
	for participant in Participant.objects.filter(meeting_id = meeting.id):
		participant.delete()
	meeting.delete()

	resp = '<?xml version="1.0" encoding="UTF-8"?>\r\n'
	resp += '<response>\r\n'
	resp += '\t<success>%s</success>\r\n' % ("Successfully deleted calendar event")
	resp += '</response>\r\n'
	
	return HttpResponse(resp, content_type="text/xml")	
#End of deleteCalendarEvent()


#GET /^showMyEvents
def showMyEvents(request):
	logr.info("Incoming request to get all my calendar events by %s"%request.user.email)

	particiapnts = Participant.objects.filter(user_id = request.user.id)
	resp = '<?xml version="1.0" encoding="UTF-8"?>\r\n'
	resp += '<CalendarEvents>\r\n'
	for participant in particiapnts:
		meeting = Meeting.objects.get(id = participant.meeting.id)
		resp += '\t<Meeting>\r\n'
		resp += _add_xml_field("Id", meeting.id,1)
		resp += _add_xml_field("EventId", meeting.event_id ,1)
		resp += _add_xml_field("StartTime", meeting.start_time ,1)
		resp += _add_xml_field("EndTime", meeting.end_time ,1)
		resp += _add_xml_field("Description", meeting.description ,1)
		resp += _add_xml_field("Location", meeting.location ,1)
		resp += _add_xml_field("Type", meeting.interview_type ,1)
		resp += _add_xml_field("Count", meeting.schedule_count ,1)
		resp += '\t<Participants>\r\n'
		particiapnts = Participant.objects.filter(meeting_id = meeting.id).exclude(user_id = corpUser.user.id)
		for pa in particiapnts:
			resp += '\t\t<Participant>\r\n'
			resp += _add_xml_field("ParticipantID", pa.id ,2)
			resp += _add_xml_field("Email", pa.user.email ,2)
			resp += '\t\t</Participant>\r\n'
		resp += '\t</Participants>\r\n'
		resp += '\t</Meeting>\r\n'
	resp += '</CalendarEvents>\r\n'
	return HttpResponse(resp, content_type="text/xml")
#End of showMyEvents()


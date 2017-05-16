from datetime import datetime, date
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save


class Meeting(models.Model):
	
	#Stores the Calendar ID to edit/update 
	event_id = models.CharField(max_length=1024, blank=False)

	#Event start time
	start_time = models.DateTimeField()

	#Event end time
	end_time = models.DateTimeField()

	#Meeting Description
	description = models.CharField(max_length=2048, blank=True)
	
	#Meeting Location
	location = models.CharField(max_length=2048, blank=True)
	
	#Interview Types
	INTERVIEW_CHOICES = (
			('Mentor', 'Mentor'),
			('Telephonic', 'Telephonic'),
			('Face to Face', 'Face to Face'),
			)
	interview_type = models.CharField(max_length=16,choices=INTERVIEW_CHOICES,default="mentor_interview")

	schedule_count = models.PositiveIntegerField(default = 0)
	
	#Meeting object create time
	create_time = models.DateTimeField(auto_now_add = True)

	def __unicode__(self):
		return "Meeting %s interview on %s" % (str(self.interview_type),str(self.create_time))



class Participant(models.Model):

	#Which meeting?
	meeting = models.ForeignKey(Meeting)

	#Capture email address of the participant. May or may not be a user in our database.  See the role below.
	user = models.ForeignKey(User, unique=False)

	def __unicode__(self):
		return "Participant %s invited for %s" % (str(self.user.email), str(self.meeting))


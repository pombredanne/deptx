from django.db import models
from deptx.helpers import now 

from players.models import Mop
from assets.models import Unit, Task, Requisition, Document, CLEARANCE_LOW, CLEARANCE_MEDIUM, CLEARANCE_HIGH, CLEARANCE_MAX
from django_extensions.db.fields import CreationDateTimeField, ModificationDateTimeField
from provmanager.models import Provenance
from deptx.helpers import random_chars
import deptx.friendly_id as friendly_id
import string

class TaskInstance(models.Model):
    STATUS_ACTIVE = 0
    STATUS_SOLVED = 1
    STATUS_FAILED = 2
    STATUS_UNSOLVED = 3
    
    CHOICES_STATUS = (
        (STATUS_ACTIVE, "active"),
        (STATUS_SOLVED, "solved"),
        (STATUS_FAILED, "failed"),
        (STATUS_UNSOLVED, "unsolved"),
    )
    
    task = models.ForeignKey(Task)
    mop = models.ForeignKey(Mop)
    status = models.IntegerField(choices=CHOICES_STATUS, default=STATUS_ACTIVE)
    serial = models.CharField(max_length=32, blank=True, null=True, unique=True)
    provenance = models.OneToOneField(Provenance, blank=True, null=True, related_name="taskInstance")
    createdAt = CreationDateTimeField()
    modifiedAt = ModificationDateTimeField()
    
    def getTrust(self):
        if self.status == self.STATUS_SOLVED:
            return self.task.getTrustSolved()
        elif self.status == self.STATUS_FAILED:
            return self.task.getTrustFailed()
        elif self.status == self.STATUS_UNSOLVED:
            return self.task.getTrustUnsolved()
        else:
            return 0
    
    def save(self, *args, **kwargs):
        super(TaskInstance, self).save(*args, **kwargs)
        if self.id and not self.serial:
            self.serial = "T-%s-%s-%s" % (random_chars(size=3, chars=string.ascii_uppercase), friendly_id.encode(self.id), random_chars(chars=self.task.unit.serial))
            super(TaskInstance, self).save(*args, **kwargs)

        documentInstance, created = DocumentInstance.objects.get_or_create(mop=self.mop, taskInstance=self)
        #TODO what if object was not created?
        if not self.status == self.STATUS_ACTIVE:
            self.mop.totalTrust += self.getTrust()
            self.mop.trust += self.getTrust()
            self.mop.save()

    def __unicode__(self):
        return "%s - %s - %s - %s" % (self.task.name, self.mop.user.username, self.get_status_display(), self.serial)

class DocumentInstance(models.Model):
    mop = models.ForeignKey(Mop)
    used = models.BooleanField(default=False)
    createdAt = CreationDateTimeField()
    modifiedAt = ModificationDateTimeField()
    #stuff needed if it is a mop-document
    serial = models.CharField(max_length=36, blank=True, null=True, unique=True)
    taskInstance = models.OneToOneField(TaskInstance, related_name='documentInstance', blank=True, null=True)
    acquired = models.BooleanField(default=False)
    modified = models.BooleanField(default=False)
    correct = models.BooleanField(default=False)
    provenanceState = models.TextField(blank=True, null=True)
    #stuff needed if it is a cron document
    document = models.ForeignKey(Document, blank=True, null=True)
    
    def getTrust(self):
        if self.getClearance() == CLEARANCE_LOW:
            return 0
        elif self.getClearance() == CLEARANCE_MEDIUM:
            return 10
        elif self.getClearance() == CLEARANCE_HIGH:
            return 20
        else:
            return 30
    
    def getClearance(self):
        if self.isMop():
            return self.taskInstance.task.clearance
        elif self.isCron():
            return CLEARANCE_MAX
        else:
            return None
    
    def isMop(self):
        if not self.taskInstance == None:
            return True
        else:
            return False
    
    def isCron(self):
        if not self.document == None:
            return True
        else:
            return False
    
    def save(self, *args, **kwargs):
        super(DocumentInstance, self).save(*args, **kwargs)
        if self.id and not self.serial:
            self.serial = "DOC-%s-%s-%s-%s" % (random_chars(size=2, chars=string.ascii_uppercase), friendly_id.encode(self.id), random_chars(chars="PROVENANCE8003"), random_chars(chars="MIXEDREALITYLAB0000099999"))
            super(DocumentInstance, self).save(*args, **kwargs)
        self.mop.totalTrust += self.getTrust()
        self.mop.trust += self.getTrust()
        self.mop.save()
    
    def __unicode__(self):
        if self.isMop():
            return self.serial
        elif self.isCron():
            return self.document.serial
        else:
            return 'ERROR'
        
class RequisitionBlank(models.Model):
    mop = models.ForeignKey(Mop)
    requisition = models.ForeignKey(Requisition)
    createdAt = CreationDateTimeField()
    modifiedAt = ModificationDateTimeField()
    
    def __unicode__(self):
        return self.requisition.name + " - " + self.mop.user.username 

class RequisitionInstance(models.Model):
    blank = models.ForeignKey(RequisitionBlank)
    data = models.CharField(max_length=256, blank=True, null=True)
    used = models.BooleanField(default=False)
    createdAt = CreationDateTimeField()
    modifiedAt = ModificationDateTimeField()
    
    def __unicode__(self):
        return self.blank.requisition.unit.serial + ": " + self.blank.requisition.serial + " (" + str(self.modifiedAt) + ")"
    

class Mail(models.Model):
    TYPE_RECEIVED = 0
    TYPE_SENT = 1
    TYPE_DRAFT = 2
    
    CHOICES_TYPE = (
        (TYPE_RECEIVED, "received"),
        (TYPE_SENT, "sent"),
        (TYPE_DRAFT, "draft")
    )
    
    STATE_NORMAL = 0
    STATE_TRASHED = 1
    STATE_DELETED = 2
    
    CHOICES_STATE = (
        (STATE_NORMAL, "normal"),
        (STATE_TRASHED, "trashed"),
        (STATE_DELETED, "deleted")
    )
  
    SUBJECT_EMPTY = 1
    
    SUBJECT_REQUEST_FORM = 101
    SUBJECT_REQUEST_TASK = 102
    SUBJECT_REQUEST_DOCUMENT = 103
    SUBJECT_SUBMIT_REPORT = 104
        
    SUBJECT_RECEIVE_FORM = 201
    SUBJECT_RECEIVE_TASK = 202
    SUBJECT_RECEIVE_DOCUMENT = 203
    
    SUBJECT_ERROR = 211
    SUBJECT_INFORMATION = 212
    SUBJECT_REPORT_EVALUATION = 213
    SUBJECT_UNCAUGHT_CASE = 214
    
    CHOICES_SUBJECT_SENDING = (
        (SUBJECT_EMPTY, "---------"),
        (SUBJECT_REQUEST_FORM, "Requesting Form"),
        (SUBJECT_REQUEST_TASK, "Requesting Task"),
        (SUBJECT_REQUEST_DOCUMENT, "Requesting Document"),
        (SUBJECT_SUBMIT_REPORT, "Submitting Report"),
    )
    
    
    CHOICES_SUBJECT_RECEIVING = (
        (SUBJECT_RECEIVE_FORM, "Assigning Form"),
        (SUBJECT_RECEIVE_TASK, "Assigning Task"),
        (SUBJECT_RECEIVE_DOCUMENT, "Assigning Document"),
        (SUBJECT_ERROR, "Error"),
        (SUBJECT_INFORMATION, "Information"),
        (SUBJECT_REPORT_EVALUATION, "Task Evaluation Result"),
        (SUBJECT_UNCAUGHT_CASE, "dfjhsjdvnvewe;efhjk")
    )
    
    CHOICES_SUBJECT = CHOICES_SUBJECT_SENDING + CHOICES_SUBJECT_RECEIVING
    
    
    mop = models.ForeignKey(Mop)
    unit = models.ForeignKey(Unit, blank=True, null=True)

    subject = models.IntegerField(choices=CHOICES_SUBJECT, default=SUBJECT_EMPTY, blank=True, null=True)
    body = models.TextField(blank=True, null=True)
    read = models.BooleanField(default=False)
    state = models.IntegerField(choices=CHOICES_STATE, default=STATE_NORMAL)
    type = models.IntegerField(choices=CHOICES_TYPE)
    processed = models.BooleanField(default=False)
    
    requisitionInstance = models.ForeignKey(RequisitionInstance, null=True, blank=True)
    documentInstance = models.ForeignKey(DocumentInstance, null=True, blank=True)  
    
    createdAt = CreationDateTimeField()
    modifiedAt = ModificationDateTimeField()
    
    def __unicode__(self):
        if self.subject == None:
            subject = "no subject"
        else:
            subject = self.get_subject_display()
        return "%s - %s - %s - processed: %s" % (self.get_type_display(), self.mop.user.username, subject, str(self.processed))

class Badge(models.Model):
    BADGE_0 = 0
    BADGE_1 = 1
    BADGE_2 = 2
    BADGE_3 = 3
    BADGE_4 = 4
    BADGE_5 = 5
    BADGE_6 = 6
    BADGE_7 = 7
    BADGE_8 = 8
    BADGE_9 = 9
    BADGE_10 = 10
    BADGE_11 = 11
    
    CHOICES_BADGE = (
        (BADGE_0, 'Black ORCHID'),
        (BADGE_1, 'Green ORCHID'),
        (BADGE_2, 'Blue ORCHID'),
        (BADGE_3, 'Orange ORCHID'),
        (BADGE_4, 'Yellow ORCHID'),
        (BADGE_5, 'Beige ORCHID'),
        (BADGE_6, 'Purple ORCHID'),
        (BADGE_7, 'Turquois ORCHID'),
        (BADGE_8, 'Mint ORCHID'),
        (BADGE_9, 'Brown ORCHID'),
        (BADGE_10, 'White ORCHID'),
        (BADGE_10, 'Ultraviolet ORCHID'),                 
    )
    
    
    mop = models.ForeignKey(Mop)
    badge = models.IntegerField(choices=CHOICES_BADGE)
    createdAt = CreationDateTimeField()
    modifiedAt = ModificationDateTimeField()
    
    def __unicode__(self):
        return "%s - %s" % (self.mop.user.username, self.get_badge_display())
    
    
from django.shortcuts import render, render_to_response, redirect

from django.http import HttpResponseRedirect, HttpResponse
from django.core.urlresolvers import reverse

from django.template import RequestContext
from django.contrib import auth
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.core.context_processors import csrf
from django.views.decorators.csrf import csrf_protect

from players.models import Player, Mop
from django.contrib.auth.models import User

from assets.models import Task, Requisition, Document, Unit
from mop.models import TaskInstance, Mail, RequisitionInstance, RequisitionBlank, DocumentInstance, Badge#, WeekTrust
from mop.forms import MailForm, RequisitionInstanceForm

from prov.model import ProvBundle, Namespace, Literal, PROV, XSD, Identifier

#from persistence.models import save_bundle
from prov.model.graph import prov_to_file
from deptx.helpers import generateUUID, now
from deptx.settings import MEDIA_ROOT
from cron.models import CronDocumentInstance

from provmanager.views import getProvJson, getProvSvg, MODE_MOP
from provmanager.provlogging import provlog_add_mop_login, provlog_add_mop_logout, provlog_add_mop_sign_form, provlog_add_mop_send_form, provlog_add_mop_issue_form, provlog_add_mop_issue_document

from logger.logging import log_cron, log_mop
import json
from datetime import date, timedelta

from mop.mailserver import analyze_mail
from mop.performer import analyze_performance
from django.views.decorators.csrf import csrf_exempt

def isMop(user):
    if user:
        for mop in Mop.objects.filter(user=user):
            if mop.active:
                return True
    return False

#@login_required(login_url='mop_login')
#@user_passes_test(isMop, login_url='mop_login')
def index(request):
    
    if not request.user == None and request.user.is_active and isMop(request.user):
        #MAIL MANAGING
        inbox_unread = Mail.objects.filter(mop=request.user.mop).filter(state=Mail.STATE_NORMAL).filter(type=Mail.TYPE_RECEIVED).filter(read=False).count()
        outbox_unread = Mail.objects.filter(mop=request.user.mop).filter(state=Mail.STATE_NORMAL).filter(type=Mail.TYPE_SENT).filter(read=False).count()
        trash_unread = Mail.objects.filter(mop=request.user.mop).filter(state=Mail.STATE_TRASHED).filter(read=False).count()
        draft_unread = Mail.objects.filter(mop=request.user.mop).filter(state=Mail.STATE_NORMAL).filter(type=Mail.TYPE_DRAFT).filter(read=False).count()

        log_mop(request.user.mop, 'index')
        context = {'user': request.user, 'inbox_unread': inbox_unread, 'outbox_unread': outbox_unread, 'trash_unread': trash_unread, 'draft_unread': draft_unread}
        return render(request, 'mop/index.html', context)
    
    else:
        return login(request)

def login(request):
    if request.method == 'POST':
        form = AuthenticationForm(data=request.POST)
        
        username = request.POST.get('username', '')
        password = request.POST.get('password', '')
        user = auth.authenticate(username=username, password=password)
        
        # this is used to check if the user is a cron user or a mop user
        # (also in if-clause
        # TODO: at the moment there is no proper error message when trying to login with a non-cron account
        # TODO: Code is almost identical to CRON-code
        if not user == None and user.is_active and isMop(user):
            auth.login(request, user)
            log_mop(request.user.mop, 'login')
            provlog_add_mop_login(request.user.mop, request.session.session_key)
            
            #Checking mail when logging in
            analyze_mail(request.user.mop)
            return HttpResponseRedirect(reverse('mop_index'))
            
        else:
            return render_to_response('mop/login.html', {'form' : form}, context_instance=RequestContext(request))
        
    else:
        form =  AuthenticationForm()
        return render_to_response('mop/login.html', {'form' : form}, context_instance=RequestContext(request))

def logout_view(request):
    log_mop(request.user.mop, 'logout')
    provlog_add_mop_logout(request.user.mop, request.session.session_key)
    logout(request)
    return redirect('mop_index')

@login_required(login_url='mop_login')
@user_passes_test(isMop, login_url='mop_login')
def rules(request):
    unit_list = Unit.objects.all()
    requisition_list = Requisition.objects.all()
    log_mop(request.user.mop, 'read rules')
    return render(request, 'mop/rules.html', {"unit_list":unit_list, "requisition_list": requisition_list})

@login_required(login_url='mop_login')
@user_passes_test(isMop, login_url='mop_login')
def performance(request):
    badge_list = Badge.objects.filter(mop=request.user.mop).order_by('-modifiedAt')
    
#     taskInstance_list = TaskInstance.objects.filter(mop=request.user.mop).exclude(status=TaskInstance.STATUS_ACTIVE).order_by('modifiedAt')
#     print taskInstance_list
#     
#     #creationDate = request.user.mop.created
#     creationDate = request.user.mop.created - timedelta(weeks=-3)
#     today = now()
#     print creationDate
#     print today
#     nextMonday = timedelta(days=-today.weekday(), weeks=1)
#     lastMonday = today - timedelta(days=today.weekday())
#     print nextMonday
#     print lastMonday
#     weekTrust_list = WeekTrust.objects.filter(mop=request.user.mop).order_by('-year', '-week')
    log_mop(request.user.mop, 'read performance')
    return render(request, 'mop/performance.html', {'badge_list':badge_list})

@login_required(login_url='mop_login')
@user_passes_test(isMop, login_url='mop_login')
def tasks(request):

    #TODO handle the other states of the task instances as well
    active_taskInstance_list = TaskInstance.objects.filter(mop=request.user.mop, status=TaskInstance.STATUS_ACTIVE)
    failed_taskInstance_list = TaskInstance.objects.filter(mop=request.user.mop, status=TaskInstance.STATUS_FAILED)
    solved_taskInstance_list = TaskInstance.objects.filter(mop=request.user.mop, status=TaskInstance.STATUS_SOLVED)
    
    new_task_list = []
    tasks = Task.objects.all()
    
    #TODO optimize so that not everything needs to be read everytime
    for task in tasks:
        try:
            taskInstance = TaskInstance.objects.get(task=task, mop=request.user.mop)
        except TaskInstance.DoesNotExist:
            taskInstance = None
        
        if taskInstance == None:
            new_task_list.append(task)
    
    log_mop(request.user.mop, 'view tasks')   
    return render(request, 'mop/tasks.html', {"active_taskInstance_list": active_taskInstance_list, "failed_taskInstance_list": failed_taskInstance_list, "solved_taskInstance_list": solved_taskInstance_list, "new_task_list": new_task_list})

@login_required(login_url='mop_login')
@user_passes_test(isMop, login_url='mop_login')
def documents(request):
    documentInstance_list = DocumentInstance.objects.filter(mop=request.user.mop).filter(used=False)
    
    log_mop(request.user.mop, 'view documents')
    return render(request, 'mop/documents.html', {"documentInstance_list": documentInstance_list})


@login_required(login_url='mop_login')
@user_passes_test(isMop, login_url='mop_login')
def document_provenance(request, documentInstance_id):
    try:
        documentInstance = DocumentInstance.objects.get(id=documentInstance_id, mop=request.user.mop)
        documentInstance.save()
    except DocumentInstance.DoesNotExist:
        documentInstance = None

    if not documentInstance == None:

        doc ={}
        doc['id'] = documentInstance.document.id
        doc['name'] = documentInstance.document.name
        doc['store_id'] = documentInstance.document.provenance.store_id    
        log_mop(request.user.mop, 'view provenance', json.dumps(doc))

    return render(request, 'mop/documents_provenance.html', {'documentInstance': documentInstance, 'mode':MODE_MOP})


@login_required(login_url='mop_login')
@user_passes_test(isMop, login_url='mop_login')
def mail_inbox(request):
    #checking mail when checking inbox
    analyze_mail(request.user.mop)
    mail_list = Mail.objects.filter(mop=request.user.mop).filter(state=Mail.STATE_NORMAL).filter(type=Mail.TYPE_RECEIVED).order_by('-createdAt')
    log_mop(request.user.mop, 'view inbox')
    return render(request, 'mop/mail_inbox.html', {"mail_list": mail_list})

@login_required(login_url='mop_login')
@user_passes_test(isMop, login_url='mop_login')
def mail_outbox(request):
    mail_list = Mail.objects.filter(mop=request.user.mop).filter(state=Mail.STATE_NORMAL).filter(type=Mail.TYPE_SENT).order_by('-createdAt')
    log_mop(request.user.mop, 'view outbox')
    return render(request, 'mop/mail_outbox.html', {"mail_list": mail_list})

@login_required(login_url='mop_login')
@user_passes_test(isMop, login_url='mop_login')
def mail_draft(request):
    mail_list = Mail.objects.filter(mop=request.user.mop).filter(state=Mail.STATE_NORMAL).filter(type=Mail.TYPE_DRAFT).order_by('-createdAt')
    log_mop(request.user.mop, 'view drafts')
    return render(request, 'mop/mail_draft.html', {"mail_list": mail_list})


@login_required(login_url='mop_login')
@user_passes_test(isMop, login_url='mop_login')
def mail_trash(request):
    mail_list = Mail.objects.filter(mop=request.user.mop).filter(state=Mail.STATE_TRASHED).order_by('-createdAt')
    log_mop(request.user.mop, 'view trash')
    return render(request, 'mop/mail_trash.html', {"mail_list": mail_list})

@login_required(login_url='mop_login')
@user_passes_test(isMop, login_url='mop_login')
def mail_view(request, mail_id):
    try:
        mail = Mail.objects.get(id=mail_id, mop=request.user.mop)
        mail.read = True
        mail.save()
    except Mail.DoesNotExist:
        mail = None
    
    
    if not mail == None:
        m ={}
        m['id'] = mail.id
        m['subject'] = mail.subject
        log_mop(request.user.mop, 'view mail', json.dumps(m))
    
    return render(request, 'mop/mail_view.html', {'mail': mail})

@login_required(login_url='mop_login')
@user_passes_test(isMop, login_url='mop_login')
def mail_trashing(request, mail_id):
    try:
        mail = Mail.objects.get(id=mail_id, mop=request.user.mop, state=Mail.STATE_NORMAL)
    except Mail.DoesNotExist:
        #TODO Error handling
        return redirect('mop_index')
    mail.state = Mail.STATE_TRASHED
    mail.save()
    
    if not mail == None:
        m ={}
        m['id'] = mail.id
        m['subject'] = mail.subject
        log_mop(request.user.mop, 'trash mail', json.dumps(m))
    
    if mail.type == Mail.TYPE_RECEIVED:
        return redirect('mop_mail_inbox')
    elif mail.type == Mail.TYPE_SENT:
        return redirect('mop_mail_outbox')
    elif mail.type == Mail.TYPE_DRAFT:
        return redirect('mop_mail_draft')
    

@login_required(login_url='mop_login')
@user_passes_test(isMop, login_url='mop_login')
def mail_untrashing(request, mail_id):
    try:
        mail = Mail.objects.get(id=mail_id, mop=request.user.mop, state=Mail.STATE_TRASHED)
    except Mail.DoesNotExist:
        return redirect('mop_index')
    mail.read = True
    mail.state = Mail.STATE_NORMAL
    mail.save()
    
    if not mail == None:
        m ={}
        m['id'] = mail.id
        m['subject'] = mail.subject
        log_mop(request.user.mop, 'untrash mail', json.dumps(m))
    
    return redirect('mop_mail_trash')

@login_required(login_url='mop_login')
@user_passes_test(isMop, login_url='mop_login')
def mail_deleting(request, mail_id):
    try:
        mail = Mail.objects.get(id=mail_id, mop=request.user.mop, state=Mail.STATE_TRASHED)
    except Mail.DoesNotExist:
        #TODO Error handling
        return redirect('mop_index')
    mail.read = True
    mail.state = Mail.STATE_DELETED
    mail.save()
    
    if not mail == None:
        m ={}
        m['id'] = mail.id
        m['subject'] = mail.subject
        log_mop(request.user.mop, 'delete mail', json.dumps(m))
    
    return redirect('mop_mail_trash')

@login_required(login_url='mop_login')
@user_passes_test(isMop, login_url='mop_login')
def mail_compose(request):
    #TODO Mail needs a sentAt / savedAt value so that trashing email does not change its date
    if request.method == 'POST':
        mail = Mail(mop=request.user.mop, type=Mail.TYPE_SENT)
        if 'send' in request.POST:
            mail.type = Mail.TYPE_SENT
            mail.read = True
        elif 'draft' in request.POST:
            mail.type = Mail.TYPE_DRAFT
            mail.read = False
        form = MailForm(data=request.POST, instance=mail)
        
        if form.is_valid():
            mail.processed = False
            mail = form.save()
            if not mail.requisitionInstance == None:
                mail.requisitionInstance.used = True
                mail.requisitionInstance.save()
                
            return redirect('mop_index')
        else:
            #TODO code duplication between here and the else below
            form.fields["requisitionInstance"].queryset = RequisitionInstance.objects.filter(blank__mop=request.user.mop).filter(used=False).order_by('-modifiedAt')
            form.fields["documentInstance"].queryset = DocumentInstance.objects.filter(mop=request.user.mop).filter(used=False).order_by('-modifiedAt')
            form.fields["subject"].choices = Mail.CHOICES_SUBJECT_SENDING
            return render_to_response('mop/mail_compose.html', {'form' : form,}, context_instance=RequestContext(request))
        
    else:
        form =  MailForm()
        form.fields["requisitionInstance"].queryset = RequisitionInstance.objects.filter(blank__mop=request.user.mop).filter(used=False).order_by('-modifiedAt')
        form.fields["documentInstance"].queryset = DocumentInstance.objects.filter(mop=request.user.mop).filter(used=False).order_by('-modifiedAt')
        form.fields["subject"].choices = Mail.CHOICES_SUBJECT_SENDING
        return render_to_response('mop/mail_compose.html', {'form' : form,}, context_instance=RequestContext(request))

#TODO code duplication between mail_edit and mail_compose    
@login_required(login_url='mop_login')
@user_passes_test(isMop, login_url='mop_login')
def mail_edit(request, mail_id):
    try:
        mail = Mail.objects.get(id=mail_id)
    except mail.DoesNotExist:
        #TODO error handling
        return redirect('mop_mail_index')
    
    if request.method == 'POST':
        if 'send' in request.POST:
            mail.type = Mail.TYPE_SENT
            mail.read = True
        elif 'draft' in request.POST:
            mail.type = Mail.TYPE_DRAFT
            mail.read = False
        
        form = MailForm(data=request.POST, instance=mail)
        print mail.id
        if form.is_valid():
            mail.processed = False
            mail = form.save()
            return redirect('mop_index')
        else:
            form.fields["requisitionInstance"].queryset = RequisitionInstance.objects.filter(blank__mop=request.user.mop).filter(used=False).order_by('-modifiedAt')
            form.fields["documentInstance"].queryset = DocumentInstance.objects.filter(mop=request.user.mop)
            form.fields["subject"].choices = Mail.CHOICES_SUBJECT_SENDING
            return render_to_response('mop/mail_compose.html', {'form' : form, 'mail':mail}, context_instance=RequestContext(request))
        
    else:
        form = MailForm(instance=mail)
        #TODO same with documents at all occurences
        form.fields["requisitionInstance"].queryset = RequisitionInstance.objects.filter(blank__mop=request.user.mop).filter(used=False).order_by('-modifiedAt')
        form.fields["documentInstance"].queryset = DocumentInstance.objects.filter(mop=request.user.mop)
        form.fields["subject"].choices = Mail.CHOICES_SUBJECT_SENDING
        return render_to_response('mop/mail_compose.html', {'form' : form, 'mail':mail}, context_instance=RequestContext(request))

#@login_required(login_url='mop_login')
#@user_passes_test(isMop, login_url='mop_login')
@csrf_exempt
def mail_check(request):
    #TODO: compare with previous unread emails
    #TODO: Emails need to be processed independent of player!!!
    if request.is_ajax():
        mail_count = analyze_mail(request.user.mop)
        total_unread = Mail.objects.filter(mop=request.user.mop).filter(state=Mail.STATE_NORMAL).filter(type=Mail.TYPE_RECEIVED).filter(read=False).count() 
        json_data = json.dumps({"mail_count":mail_count, 'total_unread':total_unread})
    
        return HttpResponse(json_data, mimetype="application/json")


@login_required(login_url='mop_login')
@user_passes_test(isMop, login_url='mop_login')
def forms_blank(request):
    
    # Create a blank form for all Forms that the mop user should have at start
    initialRequisitions = Requisition.objects.filter(isInitial=True)
    for initial in initialRequisitions:
        RequisitionBlank.objects.get_or_create(mop=request.user.mop, requisition=initial)
            
    blank_list = RequisitionBlank.objects.filter(mop=request.user.mop)            
    
    log_mop(request.user.mop, 'blank forms')
    return render(request, 'mop/forms_blank.html', {"blank_list": blank_list})

@login_required(login_url='mop_login')
@user_passes_test(isMop, login_url='mop_login')
def form_fill(request, reqBlank_id):
    #TODO check if user has rights to access the requisition in the first place
    try:
        reqBlank = RequisitionBlank.objects.get(id=reqBlank_id)
    except RequisitionBlank.DoesNotExist:
        reqBlank=None
        
    if request.method == 'POST':
        requisitionInstance = RequisitionInstance(blank=reqBlank)
        form = RequisitionInstanceForm(data=request.POST, instance=requisitionInstance)
        if form.is_valid():
            form.save()
            
            f ={}
            f['form_id'] = reqBlank.requisition.id
            f['form_name'] = reqBlank.requisition.name
            f['instance_id'] = requisitionInstance.id
            f['data'] = form.data
            log_mop(request.user.mop, 'fill form', json.dumps(f))
            provlog_add_mop_sign_form(request.user.mop, requisitionInstance, request.session.session_key)
            return redirect('mop_forms_signed')
    else:
        form = RequisitionInstanceForm()
        return render(request, 'mop/forms_fill.html', {"reqBlank": reqBlank, "form": form}, context_instance=RequestContext(request))

@login_required(login_url='mop_login')
@user_passes_test(isMop, login_url='mop_login')
def forms_signed(request):
    requisitionInstance_list = RequisitionInstance.objects.filter(blank__mop=request.user.mop).filter(used=False).order_by("-modifiedAt")
    requisitionInstance_used_list = RequisitionInstance.objects.filter(blank__mop=request.user.mop).filter(used=True).order_by("-modifiedAt")
    
    log_mop(request.user.mop, 'view filled forms')
    return render(request, 'mop/forms_signed.html', {"requisitionInstance_list": requisitionInstance_list, "requisitionInstance_used_list": requisitionInstance_used_list})


@staff_member_required
def control(request):
    output = None
    if request.method == 'POST':
        if 'mail' in request.POST:
            output = analyze_mail()
        elif 'performance' in request.POST:
            output = analyze_performance()
    return render(request, 'mop/control.html', {'output':output})       

# def getTotalTrust(mop):
#     trust = 0
#     trustInstance_list = TrustInstance.objects.filter(mop=mop).order_by('date')    
#     for trustInstance in trustInstance_list:
#         trust += trustInstance.getTrust()
#     return trust
# 
# def getWeekTrust(mop):
#     trust = {}
#     trustInstance_list = TrustInstance.objects.filter(mop=mop).order_by('-date')    
#     for trustInstance in trustInstance_list:
#         y, w, d = trustInstance.date.isocalendar()
#         print "%s - %s" % (trustInstance.date.isocalendar(), trustInstance.getTrust())
#         try:
#             trust[str(w)] += trustInstance.getTrust()
#         except:
#             trust[str(w)] = trustInstance.getTrust()
#     print trust
#     return trust
    
    
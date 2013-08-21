from django.shortcuts import render, render_to_response, redirect

from django.http import HttpResponseRedirect
from django.core.urlresolvers import reverse

from django.template import RequestContext
from django.contrib import auth
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import authenticate, login
from django.contrib.auth.forms import AuthenticationForm
from django.core.context_processors import csrf
from django.views.decorators.csrf import csrf_protect

from players.models import Player, Cron, Mop
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm

from players.forms import MopForm

from assets.models import Case, Mission
from cron.models import CaseInstance, CronDocumentInstance, CronTracker
from mop.models import DocumentInstance

def isCron(user):
    if user:
        return Cron.objects.filter(user=user).exists()
    return False

def login(request):
    if request.method == 'POST':
        form = AuthenticationForm(data=request.POST)
        
        username = request.POST.get('username', '')
        password = request.POST.get('password', '')
        user = auth.authenticate(username=username, password=password)
        
        # this is used to check if the user is a cron user
        # TODO: at the moment there is no proper error message when trying to login with a non-cron account
        if user is not None and user.is_active and isCron(user):
            auth.login(request, user)
            return HttpResponseRedirect(reverse('cron_index'))
            
        else:
            return render_to_response('cron/login.html', {'form' : form,}, context_instance=RequestContext(request))
        
    else:
        form =  AuthenticationForm()
        return render_to_response('cron/login.html', {'form' : form,}, context_instance=RequestContext(request))

@login_required(login_url='cron_login')
@user_passes_test(isCron, login_url='cron_login')
def index(request):
    user = request.user
    cron = user.cron
    context = { "cront": cron, "user":user }
    
    return render(request, 'cron/index.html', context)
    
#     if (cron.crontracker.mission.rank==0 and cron.crontracker.progress==0):
#         return render(request, 'cron/episode0.html', context)
#     elif (cron.crontracker.mission.rank==0 and cron.crontracker.progress==1):
#         return render(request, 'cron/index.html', context)
#     else:
#         return render(request, 'cron/index.html', context)

@login_required(login_url='cron_login')
@user_passes_test(isCron, login_url='cron_login')
def mopmaker(request):
    print request
    if request.method == 'POST' and 'proceed' not in request.POST:
        mop_form = MopForm(request.POST, prefix="mop")
        user_form = UserCreationForm(request.POST, prefix="user")
        
        if mop_form.is_valid() and user_form.is_valid():
            #TODO check if all saves work and catch the error if they don't
            new_user = user_form.save()
            player = request.user.cron.player
            mop = mop_form.save(commit=False)
            mop.player = player
            mop.user = new_user
            mop.save()

            crontracker = request.user.cron.crontracker
            crontracker.progress = crontracker.progress + 1
            crontracker.save()
            return redirect('cron_mission')
        else:
            return render_to_response(   'cron/mission_0/2.html',
                                        {"mop_form": mop_form, "user_form": user_form, "user": request.user},
                                        context_instance=RequestContext(request)
                                        )
    
    else:
        mop_form = MopForm(prefix="mop")
        user_form = UserCreationForm(prefix="user")
        return render_to_response(  'cron/mission_0/2.html',
                                    {"mop_form": mop_form, "user_form": user_form, "user": request.user},
                                    context_instance=RequestContext(request)
                                )


@login_required(login_url='cron_login')
@user_passes_test(isCron, login_url='cron_login')
def mission(request):
    
    #TODO: mission texts should come from the database and not from the file system! As otherwise they would need to be checked in...
    try:
        crontracker = CronTracker.objects.get(cron=request.user.cron)
    except CronTracker.DoesNotExist:
        firstMission = Mission.objects.get(rank=0)
        crontracker = CronTracker(cron=request.user.cron, progress=0, mission=firstMission)
        crontracker.save()
       
    #TODO remove magic numbers
    if request.method == 'POST':
        #progress 2 means the player needs to solve the cases and cannot progress just by pressing a button
        if (crontracker.progress == 2):
            pass
        else:
            crontracker.progress = crontracker.progress + 1
            crontracker.save()
    
    #progress 2 means we should show the list of all the cases
    if (crontracker.progress == 2):
        #do something unusual in case we are in the tutorial mission
        if (crontracker.mission.rank == 0):
            return mopmaker(request)
        
        case_list = Case.objects.filter(mission=crontracker.mission).order_by("rank")
        unfinished = False
        for case in case_list:
            try:
                caseInstance = CaseInstance.objects.get(case=case)
                case.solved = caseInstance.solved
            except CaseInstance.DoesNotExist:
                unfinished = True
        
        if unfinished:
            return render_to_response('cron/case_list.html', {"user": request.user, "mission": crontracker.mission, "case_list": case_list},
                                        context_instance=RequestContext(request)
                                )
        else:
            crontracker.progress = 3
            crontracker.save()
            return redirect('cron_mission')
        
    elif (crontracker.progress == 5):
        finishMission(crontracker)
        return redirect('cron_index')
    else:
        folder = "mission_" + str(crontracker.mission.rank) + "/"
        snippet = str(crontracker.progress) + ".html"
        template_url = "cron/" + folder + snippet
    
        return render_to_response('cron/mission.html', {"user": request.user, "mission": crontracker.mission, "template_url": template_url},
                                        context_instance=RequestContext(request)
                                )
def finishMission(crontracker):
    currentMission = crontracker.mission
    newRank = currentMission.rank + 1
    newMission = Mission.objects.get(rank=newRank)
    crontracker.mission = newMission
    crontracker.progress = 0
    crontracker.save()

@login_required(login_url='cron_login')
@user_passes_test(isCron, login_url='cron_login')
#TODO: Has user access to case?
def case(request, serial):
    case = Case.objects.get(serial=serial)
    crontracker = request.user.cron.crontracker
    caseInstance, created = CaseInstance.objects.get_or_create(case=case, crontracker=crontracker)
    
    url = "cron/mission_" + str(case.mission.rank) + "/cases/" + str(case.rank) + "_"
    
    if not (caseInstance.solved):
        template_url = url + "intro.html"
        requiredDocuments = getAllDocumentStates(request.user.cron, case)

        return render_to_response('cron/case_intro.html', {"user": request.user, "case": case, "template_url": template_url, "document_list": requiredDocuments },
                                        context_instance=RequestContext(request))
    else:
        template_url = url + "outro.html"
        return render_to_response('cron/case_outro.html', {"user": request.user, "case": case, "template_url": template_url, },
                                        context_instance=RequestContext(request))
    
    
    
    

@login_required(login_url='cron_login')
@user_passes_test(isCron, login_url='cron_login')
#TODO: Has user access to case?
def provenance(request, serial):
    
    case = Case.objects.get(serial=serial)
    if request.method == 'POST':
        #TODO check if it was really solved
        caseInstance = CaseInstance.objects.get(case=case)
        caseInstance.solved = True
        caseInstance.save()
        return redirect('cron_case_detail', serial)
    
    document_list = getAllDocumentStates(request.user.cron, case)
    
    return render_to_response('cron/provenance.html', {"user": request.user, "case": case, "document_list": document_list },
                                        context_instance=RequestContext(request)
                                )

def getAllDocumentStates(cron, case):
    requiredDocuments = case.document_set.all()
    #TODO when document is put in draft, add it to CronDocumentInstance
    availableDocumentInstances = CronDocumentInstance.objects.filter(cron=cron)
            
    for required in requiredDocuments:
        for available in availableDocumentInstances:
            if (required==available.document):
                required.available = True
    
    return requiredDocuments
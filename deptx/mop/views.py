from django.shortcuts import render, render_to_response

from django.http import HttpResponseRedirect
from django.core.urlresolvers import reverse

from django.template import RequestContext
from django.contrib import auth
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import authenticate, login
from django.contrib.auth.forms import AuthenticationForm
from django.core.context_processors import csrf
from django.views.decorators.csrf import csrf_protect

from players.models import Player, Mop
from django.contrib.auth.models import User

def isMop(user):
    if user:
        for mop in Mop.objects.filter(user=user):
            if mop.active:
                return True
    return False

def custom_proc(request):
    "A context processor that provides 'app', 'user' and 'ip_address'."
    return {
        'app': 'usermanagement',
        'user': request.user,
        'ip_address': request.META['REMOTE_ADDR'],
    }

@login_required(login_url='mop_login')
@user_passes_test(isMop, login_url='mop_login')
def index(request):
    activeMops = Mop.objects.filter(active=True)
    inactiveMops = Mop.objects.filter(active=False)
    context = {'activeMops': activeMops, 'inactiveMops': inactiveMops, 'user': request.user}
    return render(request, 'mop/index.html', context)

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
        if user is not None and user.is_active and isMop(user):
            auth.login(request, user)
            return HttpResponseRedirect(reverse('mop_index'))
            
        else:
            return render_to_response('mop/login.html', {'form' : form,}, context_instance=RequestContext(request, processors=[custom_proc]))
        
    else:
        form =  AuthenticationForm()
        return render_to_response('mop/login.html', {'form' : form,}, context_instance=RequestContext(request, processors=[custom_proc]))

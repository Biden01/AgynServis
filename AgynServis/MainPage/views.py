from django.shortcuts import render, redirect
from django.contrib import messages
from .models import Service
from .forms import ContactForm

def home(request):
    services = Service.objects.all()
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Ваше сообщение успешно отправлено!')
            return redirect('MainPage:home')
    else:
        form = ContactForm()
    
    context = {
        'services': services,
        'form': form,
    }
    return render(request, 'MainPage/home.html', context)

def services(request):
    services = Service.objects.all()
    context = {
        'services': services,
    }
    return render(request, 'MainPage/services.html', context)

def about(request):
    return render(request, 'MainPage/about.html')

def contacts(request):
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Ваше сообщение успешно отправлено!')
            return redirect('MainPage:contacts')
    else:
        form = ContactForm()
    
    context = {
        'form': form,
    }
    return render(request, 'MainPage/contacts.html', context)
